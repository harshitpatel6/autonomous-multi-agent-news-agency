"""
SEO Agent: audits every published article for on-page + technical SEO, generates
optimized title tags / meta descriptions / target keywords via LLM, and tracks a
site-wide score over time so the pipeline can tell whether things are trending up
or down instead of only ever seeing a single snapshot.

Design notes (why it's built this way):

- Technical checks (length limits, thin content, missing fields) are pure Python,
  not LLM calls. An LLM is unreliable at "is this string under 60 characters" -
  a deterministic check never hallucinates a pass. The LLM is only used for the
  part that actually requires language judgment: writing the title/description/
  keywords themselves.
- generate_meta() validates its own output against the same deterministic rules
  and retries with a corrective prompt if it fails, instead of trusting a
  one-shot generation - the same self-correcting shape as the QA<->Editor backup
  loop in agent_coordinator.py. This is what "keeps learning" means in practice
  for a single run: it doesn't ship a broken title just because the first
  attempt produced one.
- audit_site() is what makes this autonomous: it always audits brand-new
  articles first (seo_audited_at IS NULL), then falls through to the
  longest-stale already-audited ones. Content that was fine at publish time can
  go stale (a newer article steals its keyword, a title starts colliding with
  another headline) - re-checking on a cadence is what catches that without a
  human remembering to ask for it.
- Every sweep is logged to seo_audit_runs with a trend vs. the previous run, so
  the dashboard shows "improving" or "declining," not just a number.

Runs automatically from publish.py after each publish cycle - no manual trigger,
no separate cron entry needed (the whole file publishes to the site every 15 min
already; SEO auditing rides along on the same run).
"""
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from db import get_connection
from agents.base_agent import Agent
from agents.message_router import register_agent

TITLE_MAX = 60
DESC_MIN = 70
DESC_MAX = 155
THIN_CONTENT_WORDS = 300
MIN_KEYWORDS = 3
RE_AUDIT_DAYS = 14  # re-check even "clean" articles this often - the drift check
SWEEP_BATCH_SIZE = 15  # articles audited per publish.py run - bounds LLM spend per cycle

# Keep in sync with reporter_agent.py's classification categories and
# web/lib/categories.ts (same duplication that file already documents/accepts -
# there's no single shared source of truth for the taxonomy across Python/web yet).
KNOWN_CATEGORIES = [
    "Company News", "Business & Enterprise AI", "Funding & Investment", "Startup Launches",
    "Research & Models", "Tools & Engineering", "Policy & Regulation", "Other",
]

META_PROMPT_TEMPLATE = """You are an SEO specialist for an AI industry news site. Write search-optimized \
metadata for this article. Do not invent facts that aren't in the article below.

HEADLINE: {headline}
CATEGORY: {category}
SUMMARY: {summary}
ARTICLE EXCERPT: {excerpt}
{correction}
Respond ONLY with valid JSON, no other text: {{"title": "...", "description": "...", "keywords": ["...", "..."]}}

Rules:
- "title": under {title_max} characters. Lead with the single most-searched term first (the specific company, \
product, or model name involved) rather than a generic framing. No clickbait, no trailing punctuation, not \
identical to any of the existing titles listed below.
- "description": between {desc_min} and {desc_max} characters. A genuine, specific summary of what happened \
that would make someone searching this topic click - not a restatement of the headline.
- "keywords": {min_keywords}-8 realistic phrases someone would actually type into a search engine to find this \
article - mix the specific named entity with the broader topic. No generic filler like "AI news" or "technology".

EXISTING LIVE TITLES (avoid duplicating any of these):
{existing_titles}
"""


class SEOAgent(Agent):
    """Audits + optimizes on-page SEO for published articles. See module docstring for design rationale."""

    def __init__(self):
        super().__init__("SEO")

    # ------------------------------------------------------------------
    # Deterministic technical audit - no LLM, always correct
    # ------------------------------------------------------------------
    def _technical_issues(self, article: Dict) -> List[Dict]:
        issues = []
        title = article.get("seo_title") or article.get("headline") or ""
        desc = article.get("seo_description") or article.get("summary") or ""
        content = article.get("full_content") or ""
        word_count = len(_strip_html(content).split())

        if not article.get("seo_title"):
            issues.append(_issue("warn", "missing_seo_title", "No dedicated SEO title - the raw headline is used as-is in search results."))
        elif len(title) > TITLE_MAX:
            issues.append(_issue("warn", "title_too_long", f"SEO title is {len(title)} chars (max {TITLE_MAX}) - Google will truncate it."))

        if not article.get("seo_description"):
            issues.append(_issue("warn", "missing_seo_description", "No meta description set - search engines will auto-extract one, often badly."))
        elif not (DESC_MIN <= len(desc) <= DESC_MAX):
            issues.append(_issue("info", "description_length", f"Meta description is {len(desc)} chars (ideal {DESC_MIN}-{DESC_MAX})."))

        if not article.get("seo_keywords"):
            issues.append(_issue("info", "missing_keywords", "No target keywords recorded for this article."))

        if word_count < THIN_CONTENT_WORDS:
            issues.append(_issue("bad", "thin_content", f"Only {word_count} words of body content (min {THIN_CONTENT_WORDS}) - thin pages rank poorly."))

        if not article.get("category"):
            issues.append(_issue("info", "missing_category", "No category set - weakens internal topic clustering/linking."))

        return issues

    @staticmethod
    def _score(issues: List[Dict]) -> float:
        weight = {"bad": 25, "warn": 10, "info": 4}
        score = 100 - sum(weight.get(i["severity"], 5) for i in issues)
        return max(0.0, min(100.0, float(score)))

    # ------------------------------------------------------------------
    # LLM generation with a deterministic validate -> regenerate loop
    # ------------------------------------------------------------------
    def _validate_meta(self, parsed: Optional[Dict], existing_titles: List[str]) -> List[str]:
        if not parsed:
            return ["response was not valid JSON"]
        problems = []
        title, desc, kws = parsed.get("title"), parsed.get("description"), parsed.get("keywords")
        existing_lower = {t.strip().lower() for t in existing_titles if t}

        if not title or len(title) > TITLE_MAX:
            problems.append(f"title missing or over {TITLE_MAX} chars (was {len(title) if title else 0})")
        elif title.strip().lower() in existing_lower:
            problems.append("title exactly duplicates another live article's title - make it distinct")

        if not desc or not (DESC_MIN <= len(desc) <= DESC_MAX):
            problems.append(f"description missing or not between {DESC_MIN}-{DESC_MAX} chars (was {len(desc) if desc else 0})")

        if not kws or not isinstance(kws, list) or len(kws) < MIN_KEYWORDS:
            problems.append(f"keywords missing or fewer than {MIN_KEYWORDS}")

        return problems

    def generate_meta(self, article: Dict, existing_titles: List[str]) -> Optional[Dict]:
        """LLM-generate title/description/keywords, self-validating and retrying
        once with a corrective prompt if the first attempt breaks a hard rule."""
        excerpt = _strip_html(article.get("full_content") or "")[:1500] or "(no body yet - summary only)"
        correction = ""
        last_problems: List[str] = []

        for attempt in range(2):
            prompt = META_PROMPT_TEMPLATE.format(
                headline=article["headline"],
                category=article.get("category") or "General",
                summary=article.get("summary") or "",
                excerpt=excerpt,
                correction=correction,
                title_max=TITLE_MAX, desc_min=DESC_MIN, desc_max=DESC_MAX, min_keywords=MIN_KEYWORDS,
                existing_titles="\n".join(f"- {t}" for t in existing_titles[:30]) or "(none)",
            )
            response = self.call_llm(prompt, max_tokens=400, json_mode=True)
            parsed = self.parse_json(response)
            problems = self._validate_meta(parsed, existing_titles)

            if not problems:
                self.logger.log_action(
                    "generate_meta", input_data={"headline": article["headline"], "attempt": attempt + 1},
                    output_data=parsed, success=True,
                )
                return parsed

            last_problems = problems
            correction = (
                f"\nYour previous attempt was rejected for: {'; '.join(problems)}. "
                "Fix these specific problems in your next attempt.\n"
            )

        self.logger.log_action(
            "generate_meta", input_data={"headline": article["headline"]},
            success=False, error_message=f"failed validation after retries: {'; '.join(last_problems)}",
        )
        return None

    # ------------------------------------------------------------------
    # Per-article audit: check -> fix what an LLM can fix -> persist -> score
    # ------------------------------------------------------------------
    def audit_article(self, cluster_id: int) -> Optional[Dict]:
        conn = get_connection()
        row = conn.execute(
            """SELECT id, headline, category, summary, full_content, seo_title, seo_description, seo_keywords
               FROM clusters WHERE id = ? AND published_at IS NOT NULL""",
            (cluster_id,),
        ).fetchone()
        if not row:
            conn.close()
            return None
        article = dict(row)

        issues = self._technical_issues(article)
        fixable_codes = {"missing_seo_title", "missing_seo_description", "missing_keywords"}
        needs_meta = any(i["code"] in fixable_codes for i in issues)

        meta_pending = False  # LLM enrichment was needed but unavailable/failed this run
        if needs_meta:
            existing_titles = [
                r["seo_title"] or r["headline"]
                for r in conn.execute(
                    "SELECT seo_title, headline FROM clusters WHERE published_at IS NOT NULL AND id != ?",
                    (cluster_id,),
                ).fetchall()
            ]
            meta = self.generate_meta(article, existing_titles)
            if meta:
                conn.execute(
                    "UPDATE clusters SET seo_title = ?, seo_description = ?, seo_keywords = ? WHERE id = ?",
                    (meta["title"], meta["description"], json.dumps(meta["keywords"]), cluster_id),
                )
                conn.commit()
                article["seo_title"] = meta["title"]
                article["seo_description"] = meta["description"]
                article["seo_keywords"] = json.dumps(meta["keywords"])
                issues = self._technical_issues(article)  # re-check against what we just fixed
            else:
                meta_pending = True

        score = self._score(issues)
        now = datetime.now(timezone.utc).isoformat()
        if meta_pending:
            # Don't advance seo_audited_at: this failure is LLM availability (e.g. a
            # circuit-open provider), not a problem with the article itself, so it
            # should be retried on the very next sweep instead of waiting
            # RE_AUDIT_DAYS. Score/issues still get written so the dashboard reflects
            # current reality even while enrichment is pending.
            conn.execute("UPDATE clusters SET seo_score = ? WHERE id = ?", (score, cluster_id))
        else:
            conn.execute("UPDATE clusters SET seo_score = ?, seo_audited_at = ? WHERE id = ?", (score, now, cluster_id))
        conn.execute("DELETE FROM seo_page_issues WHERE cluster_id = ?", (cluster_id,))
        for i in issues:
            conn.execute(
                "INSERT INTO seo_page_issues (cluster_id, severity, code, message, detected_at) VALUES (?, ?, ?, ?, ?)",
                (cluster_id, i["severity"], i["code"], i["message"], now),
            )
        conn.commit()
        conn.close()
        return {"cluster_id": cluster_id, "score": score, "issues": issues}

    # ------------------------------------------------------------------
    # Site-wide sweep: new articles first, then the most stale re-audits.
    # This is what runs unattended from publish.py.
    # ------------------------------------------------------------------
    def audit_site(self, limit: int = SWEEP_BATCH_SIZE) -> Dict:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RE_AUDIT_DAYS)).isoformat()
        conn = get_connection()
        rows = conn.execute(
            """SELECT id FROM clusters
               WHERE published_at IS NOT NULL
                 AND (seo_audited_at IS NULL OR seo_audited_at < ?)
               ORDER BY (seo_audited_at IS NOT NULL), seo_audited_at ASC, published_at DESC
               LIMIT ?""",
            (cutoff, limit),
        ).fetchall()
        cluster_ids = [r["id"] for r in rows]
        conn.close()

        results = [self.audit_article(cid) for cid in cluster_ids]
        results = [r for r in results if r]

        conn = get_connection()
        prev = conn.execute("SELECT avg_score FROM seo_audit_runs ORDER BY run_at DESC LIMIT 1").fetchone()
        avg_score = round(sum(r["score"] for r in results) / len(results), 1) if results else None
        trend = None
        if prev and prev["avg_score"] is not None and avg_score is not None:
            trend = round(avg_score - prev["avg_score"], 1)

        # Site-wide checks that don't belong to any single article.
        site_issues = self._site_wide_issues(conn)

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO seo_audit_runs (run_at, articles_checked, avg_score, issues_found, trend, summary)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                now, len(results), avg_score,
                sum(len(r["issues"]) for r in results) + len(site_issues),
                trend, json.dumps({"site_issues": site_issues}),
            ),
        )
        conn.commit()
        conn.close()

        return {"checked": len(results), "avg_score": avg_score, "trend": trend, "site_issues": site_issues}

    def _site_wide_issues(self, conn) -> List[str]:
        """Checks that only make sense across the whole site, not per article:
        duplicate live titles, and categories with zero published articles
        (orphaned nav links - a real ranking/UX problem, not a per-page one)."""
        issues = []

        dupes = conn.execute(
            """SELECT COALESCE(seo_title, headline) AS t, COUNT(*) c
               FROM clusters WHERE published_at IS NOT NULL GROUP BY LOWER(t) HAVING c > 1"""
        ).fetchall()
        for d in dupes:
            issues.append(f"Duplicate title across {d['c']} live articles: \"{d['t']}\"")

        published_categories = {
            r["category"] for r in conn.execute(
                "SELECT DISTINCT category FROM clusters WHERE published_at IS NOT NULL"
            ).fetchall()
        }
        for label in KNOWN_CATEGORIES:
            if label not in published_categories:
                issues.append(f"Category \"{label}\" has zero published articles - orphaned nav link, wasted crawl budget.")

        return issues

    def handle_message(self, message: Dict) -> Dict:
        payload = message.get("payload", {})
        if message["type"] == "audit_article":
            result = self.audit_article(payload["cluster_id"])
            return result or {"error": "article not found or not published"}
        if message["type"] == "audit_site":
            return self.audit_site(payload.get("limit", SWEEP_BATCH_SIZE))
        return {"error": f"unknown message type {message['type']}"}


seo_agent = SEOAgent()
register_agent("seo", seo_agent.handle_message)


def _issue(severity: str, code: str, message: str) -> Dict:
    return {"severity": severity, "code": code, "message": message}


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "")
