"""
Insight Agent: the Insights desk (see config.py's "Insights desk" comment for the
product rationale). Original, non-news editorial content - explainers, research
roundups, synthesis of the site's own week, opinion, and lighter creative formats -
kept structurally separate from the News desk pipeline (reporter_agent -> writer_agent
-> clusters/articles) so this content never inherits that pipeline's "extract every
source detail" assumption, which is what produced the near-copy problem this whole
originality guardrail (utils/similarity.py) exists to fix.

Five formats, each with a deliberately different relationship to source material:
  - roundup:           several short ORIGINAL takes on recent items. Deliberately fed
                        only title + one-line teaser per item, never full article text -
                        there's nothing to over-extract from a sentence, so this format
                        is close to immune to the copying problem by construction.
  - explainer:          one evergreen AI/ML concept, written from general knowledge with
                        a couple of the site's own related stories linked as context.
  - weekly_synthesis:   synthesizes the site's OWN already-published News-desk stories
                        from the last 7 days into a trend narrative - the safest source
                        material there is, since it's already been through one round of
                        independent transformation.
  - opinion:            the desk's own point of view on a trend/debate. No external
                        source at all.
  - fun:                lighter creative formats (analogies, glossary, myth-vs-fact,
                        "explain it like...") - no external source at all.

Every format that touches source material (roundup/explainer/weekly_synthesis) runs
through the same strict originality gate as the News desk (utils.similarity, via the
shared _run_with_gate loop below) plus fact_checker_agent's grounding check. Formats
with no source (opinion/fun) run through fact_checker_agent's lighter
check_editorial_tone gate instead - there's nothing to fabricate or copy from, but
"never mock or demean a named person" still has to be enforced.
"""
import json
import random
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional, Tuple

from config import MAX_ORIGINALITY_REWRITE_ATTEMPTS
from db import get_connection
from utils.textclean import strip_html
from utils.similarity import similarity_report
from agents.base_agent import Agent
from agents.message_router import register_agent

LEGAL_RULE = """LEGAL RULE: never state or imply that a specific, named real person or organization \
committed a crime, fraud, or other wrongdoing, or is incompetent, dishonest, or unethical, unless that is \
a widely-reported, attributable fact. Critique ideas, products, strategies, and trends freely - never mock \
or demean a named individual. If you're not sure a characterization is safe, cut it rather than include it."""

ORIGINALITY_RULE = """ORIGINALITY RULE: never lift a run of source wording into your draft - every \
sentence must be your own construction. This is original commentary/writing, not a rewrite of anyone \
else's article."""

ORIGINALITY_ESCALATION = """REWRITE REQUIRED - READ THIS FIRST: your previous draft was flagged as too \
textually close to a source. Start over with different structure and your own sentence constructions \
throughout - do not reuse source phrasing or sentence rhythm even when covering the same item.

"""

BRAND_PROMPT = """You are naming a new section of an AI industry site that is entirely run by autonomous \
AI agents. The News desk already covers breaking stories; this new section is for original explainers, \
research roundups, synthesis, opinion, and lighter creative writing about the AI/ML world - written for \
people who want to actually enjoy following this industry and come away having learned something, not \
just skim headlines.

Invent a name for this section yourself. Requirements:
- 1-3 words, distinctive and memorable - NOT a generic label like "Insights," "Blog," "Editorial," or \
"Magazine."
- A short tagline, under 10 words.
- A one-sentence mission statement for what this section is for.

Respond ONLY with valid JSON, no other text:
{"name": "...", "tagline": "...", "mission": "..."}
"""


class InsightAgent(Agent):
    """Generates and persists Insights-desk content (the `features` table)."""

    def __init__(self):
        super().__init__("InsightAgent")

    # ------------------------------------------------------------------
    # Brand: the section's own name, decided once by the LLM and persisted
    # (site_meta) rather than hardcoded, so no human picks it.
    # ------------------------------------------------------------------
    def get_or_create_brand(self) -> Dict:
        conn = get_connection()
        row = conn.execute("SELECT value FROM site_meta WHERE key = 'insights_brand'").fetchone()
        conn.close()
        if row:
            try:
                stored = json.loads(row["value"])
                if stored.get("name"):
                    return stored
            except (TypeError, ValueError):
                pass  # fall through and regenerate a corrupted stored value

        response = self.call_llm(BRAND_PROMPT, max_tokens=300, json_mode=True)
        parsed = self.parse_json(response)
        if not parsed or not parsed.get("name"):
            # Don't persist a failure - return a clearly-temporary fallback so the
            # frontend always has something to render, but the NEXT call tries again
            # instead of locking in a name nothing and nobody actually chose.
            self.logger.log_action("get_or_create_brand", success=False,
                                    error_message="LLM unavailable or returned invalid JSON", level="WARNING")
            return {"name": "The Desk", "tagline": "Original coverage from the AI newsroom.",
                    "mission": "Explainers, roundups, and commentary alongside the daily news.",
                    "_pending": True}

        brand = {"name": parsed["name"], "tagline": parsed.get("tagline", ""), "mission": parsed.get("mission", "")}
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        conn.execute(
            """INSERT INTO site_meta (key, value, updated_at) VALUES ('insights_brand', ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (json.dumps(brand), now),
        )
        conn.commit()
        conn.close()
        self.logger.log_action("get_or_create_brand", output_data=brand, success=True)
        return brand

    # ------------------------------------------------------------------
    # Shared originality-gated generation loop (mirrors agents/writer_agent.py's
    # write_full_article loop) - used by every format that has real source material.
    # ------------------------------------------------------------------
    def _run_with_gate(
        self,
        build_prompt: Callable[[str], str],
        extract_text: Callable[[Dict], str],
        validate: Callable[[Optional[Dict]], Optional[str]],
        source_texts: List[str],
        max_tokens: int = 1600,
    ) -> Tuple[Optional[Dict], Optional[float]]:
        best_score = None
        for attempt in range(1, MAX_ORIGINALITY_REWRITE_ATTEMPTS + 1):
            prompt = build_prompt(ORIGINALITY_ESCALATION if attempt > 1 else "")
            response = self.call_llm(prompt, max_tokens=max_tokens, json_mode=True)
            parsed = self.parse_json(response)
            reason = validate(parsed)

            score = None
            if reason is None and source_texts:
                report = similarity_report(extract_text(parsed), source_texts)
                score = report["score"]
                best_score = score if best_score is None else min(best_score, score)
                if report["flagged"]:
                    reason = f"too similar to a source (verbatim_run={report['max_verbatim_run_words']} words)"

            self.logger.log_action(
                "generate_feature_attempt", input_data={"attempt": attempt},
                output_data={"similarity_score": score} if reason is None else None,
                success=reason is None, error_message=reason,
            )
            if reason is None:
                return parsed, score
            if "too similar to a source" not in (reason or ""):
                break
        return None, best_score

    # ------------------------------------------------------------------
    # Format: research/link roundup - teaser-only inspiration, original commentary.
    # ------------------------------------------------------------------
    def _pick_roundup_items(self, n: int = 6) -> List[Dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        conn = get_connection()
        rows = conn.execute(
            """SELECT DISTINCT title, url, source, summary_raw FROM articles
               WHERE fetched_at >= ? AND summary_raw IS NOT NULL AND length(summary_raw) > 40
               ORDER BY fetched_at DESC LIMIT 60""",
            (cutoff,),
        ).fetchall()
        conn.close()
        pool = [dict(r) for r in rows]
        random.shuffle(pool)
        return pool[:n]

    def generate_roundup(self) -> Optional[Dict]:
        items = self._pick_roundup_items(n=6)
        if len(items) < 3:
            return None
        items_block = "\n".join(
            f"- [{it['source']}] {it['title']} ({it['url']})\n  {(it['summary_raw'] or '')[:280]}" for it in items
        )
        source_texts = [(it["summary_raw"] or "") for it in items]

        def build(escalate: str) -> str:
            return f"""{escalate}You are the roundup writer for the Insights desk of an AI industry site. \
Below are recent items - title, source, link, and a one-line teaser ONLY (no full article text). Pick 4-5 \
of the most interesting and write ORIGINAL commentary on each: why it's worth a reader's attention, what's \
actually notable or surprising, how it connects to something bigger in AI/ML right now. Do not just restate \
the teaser in other words - add a genuine take a reader couldn't get from the headline alone.

{LEGAL_RULE}
{ORIGINALITY_RULE}
You only have a title, source, and one-line teaser for each item - do not invent numbers, quotes, or \
technical specifics beyond what's given here; write your commentary at the level of what you actually know, \
focused on why it matters rather than details you don't have.

ITEMS:
{items_block}

Write a 1-2 sentence intro framing the roundup, then one <h3> entry per item (heading = a short punchy \
label for the item, not just its raw headline) with 2-4 sentences of original commentary each, as clean \
HTML using only <p>, <h3>, <strong>, <a href="..."> (link each item's heading text to its URL from above).

Respond ONLY with valid JSON, no other text:
{{"title": "...", "teaser": "one sentence describing this roundup", "body_html": "<p>...</p>...", \
"tags": ["...", "..."], "picked_urls": ["...", "..."]}}
"""

        def validate(parsed: Optional[Dict]) -> Optional[str]:
            if not parsed or not parsed.get("body_html") or not parsed.get("title"):
                return "missing body_html/title"
            words = strip_html(parsed["body_html"]).split()
            if len(words) < 120:
                return f"too short ({len(words)} words)"
            if parsed["body_html"].count("<h3") < 3:
                return "fewer than 3 item entries"
            return None

        parsed, score = self._run_with_gate(
            build, lambda p: strip_html(p["body_html"]), validate, source_texts, max_tokens=1800,
        )
        if not parsed:
            return None
        picked = parsed.get("picked_urls") or [it["url"] for it in items]
        return {
            "format": "roundup", "title": parsed["title"], "teaser": parsed.get("teaser", ""),
            "body_html": parsed["body_html"], "tags": parsed.get("tags") or [],
            "sources": [{"name": it["title"], "url": it["url"]} for it in items if it["url"] in picked],
            "similarity_score": score,
        }

    # ------------------------------------------------------------------
    # Format: explainer - evergreen concept, optional light grounding via the site's
    # own related coverage (never an external source's full text).
    # ------------------------------------------------------------------
    def _pick_explainer_context(self, n: int = 3) -> List[Dict]:
        conn = get_connection()
        rows = conn.execute(
            """SELECT id, headline, summary FROM clusters
               WHERE published_at IS NOT NULL AND category IN ('Research & Models', 'Tools & Engineering')
               ORDER BY published_at DESC LIMIT 20""",
        ).fetchall()
        conn.close()
        pool = [dict(r) for r in rows]
        random.shuffle(pool)
        return pool[:n]

    def generate_explainer(self) -> Optional[Dict]:
        context = self._pick_explainer_context()
        context_block = "\n".join(f"- {c['headline']}: {c['summary']}" for c in context) or "(none)"
        source_texts = [c["summary"] for c in context]

        def build(escalate: str) -> str:
            return f"""{escalate}You are the explainer writer for the Insights desk of an AI industry site. \
Pick ONE genuinely useful AI/ML concept, technique, or piece of jargon that a working practitioner or \
curious reader would benefit from actually understanding well (e.g. "what a mixture-of-experts model \
actually does differently," "why RAG exists and where it breaks," "what 'test-time compute' means and why \
labs started caring about it") - not something trivial, not something that needs a textbook.

{LEGAL_RULE}
{ORIGINALITY_RULE}
Write from your own understanding of the concept - do not summarize or lean on any single external source. \
You may optionally reference the site's own recent coverage below to connect the concept to something real \
happening right now, but do not copy its wording either.

RECENT SITE COVERAGE (optional context, cite naturally if relevant, don't force it):
{context_block}

Write a clear, opinionated explainer (500-800 words) as clean HTML using only <p>, <h3>, <ul>/<li>, \
<strong>. Assume an intelligent reader who isn't already an expert in this specific concept. Use a concrete \
example or analogy. Take a point of view on why this matters or where it's overhyped/underhyped - don't \
just define the term neutrally.

Respond ONLY with valid JSON, no other text:
{{"title": "...", "teaser": "one sentence hook", "body_html": "<p>...</p>...", "tags": ["...", "..."]}}
"""

        def validate(parsed: Optional[Dict]) -> Optional[str]:
            if not parsed or not parsed.get("body_html") or not parsed.get("title"):
                return "missing body_html/title"
            words = strip_html(parsed["body_html"]).split()
            if len(words) < 300:
                return f"too short ({len(words)} words)"
            return None

        parsed, score = self._run_with_gate(
            build, lambda p: strip_html(p["body_html"]), validate, source_texts, max_tokens=1800,
        )
        if not parsed:
            return None
        return {
            "format": "explainer", "title": parsed["title"], "teaser": parsed.get("teaser", ""),
            "body_html": parsed["body_html"], "tags": parsed.get("tags") or [],
            "sources": [{"name": c["headline"], "url": f"/articles/{c['id']}"} for c in context],
            "similarity_score": score,
        }

    # ------------------------------------------------------------------
    # Format: weekly synthesis - the site's own already-published week, connected.
    # ------------------------------------------------------------------
    def generate_weekly_synthesis(self) -> Optional[Dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        conn = get_connection()
        rows = conn.execute(
            """SELECT id, headline, category, summary FROM clusters
               WHERE published_at IS NOT NULL AND published_at >= ?
               ORDER BY importance_score DESC LIMIT 15""",
            (cutoff,),
        ).fetchall()
        conn.close()
        stories = [dict(r) for r in rows]
        if len(stories) < 5:
            return None  # not enough of a week to synthesize anything real
        stories_block = "\n".join(f"- [{s['category']}] {s['headline']}: {s['summary']}" for s in stories)
        source_texts = [s["summary"] for s in stories]

        def build(escalate: str) -> str:
            return f"""{escalate}You are the Insights desk's weekly synthesis writer for an AI industry \
site. Below are this site's OWN stories from the past week (already independently reported and written by \
the News desk). Your job is different from re-reporting them: find the actual THROUGH-LINE - what pattern, \
tension, or shift connects several of these stories that isn't obvious from reading any one of them alone.

{LEGAL_RULE}
{ORIGINALITY_RULE}
Do not just summarize each story in turn - synthesize. Pick 1-2 real threads across the week (e.g. "three \
labs shipped smaller models this week, and here's what that says about where the compute race is actually \
heading") and argue them with specifics from the stories below.

THIS WEEK'S STORIES:
{stories_block}

Write 500-750 words as clean HTML using only <p>, <h3>, <strong>. Have a clear point of view on what the \
week actually meant, not a neutral recap.

Respond ONLY with valid JSON, no other text:
{{"title": "...", "teaser": "one sentence hook", "body_html": "<p>...</p>...", "tags": ["...", "..."]}}
"""

        def validate(parsed: Optional[Dict]) -> Optional[str]:
            if not parsed or not parsed.get("body_html") or not parsed.get("title"):
                return "missing body_html/title"
            words = strip_html(parsed["body_html"]).split()
            if len(words) < 250:
                return f"too short ({len(words)} words)"
            return None

        parsed, score = self._run_with_gate(
            build, lambda p: strip_html(p["body_html"]), validate, source_texts, max_tokens=1800,
        )
        if not parsed:
            return None
        return {
            "format": "weekly_synthesis", "title": parsed["title"], "teaser": parsed.get("teaser", ""),
            "body_html": parsed["body_html"], "tags": parsed.get("tags") or [],
            "sources": [{"name": s["headline"], "url": f"/articles/{s['id']}"} for s in stories[:8]],
            "similarity_score": score,
        }

    # ------------------------------------------------------------------
    # Formats with no external source: opinion / fun. Gated by
    # fact_checker_agent.check_editorial_tone instead of the similarity checker
    # (nothing to be textually similar TO).
    # ------------------------------------------------------------------
    def _generate_sourceless(self, format_name: str, angle_prompt: str, min_words: int, max_tokens: int) -> Optional[Dict]:
        from agents.fact_checker_agent import fact_checker_agent

        prompt = f"""{angle_prompt}

{LEGAL_RULE}

Respond ONLY with valid JSON, no other text:
{{"title": "...", "teaser": "one sentence hook", "body_html": "<p>...</p>...", "tags": ["...", "..."]}}
"""
        response = self.call_llm(prompt, max_tokens=max_tokens, json_mode=True)
        parsed = self.parse_json(response)
        if not parsed or not parsed.get("body_html") or not parsed.get("title"):
            self.logger.log_action(f"generate_{format_name}", success=False, error_message="missing body_html/title")
            return None
        words = strip_html(parsed["body_html"]).split()
        if len(words) < min_words:
            self.logger.log_action(f"generate_{format_name}", success=False,
                                    error_message=f"too short ({len(words)} words)")
            return None

        tone = fact_checker_agent.check_editorial_tone(parsed["title"], strip_html(parsed["body_html"]))
        if tone["verdict"] != "PASS":
            self.logger.log_action(f"generate_{format_name}", success=False,
                                    error_message=f"editorial tone check failed: {tone['flagged']}")
            return None

        return {
            "format": format_name, "title": parsed["title"], "teaser": parsed.get("teaser", ""),
            "body_html": parsed["body_html"], "tags": parsed.get("tags") or [],
            "sources": [], "similarity_score": None,
        }

    def generate_opinion(self) -> Optional[Dict]:
        return self._generate_sourceless(
            "opinion",
            f"""You are writing an opinion column for the Insights desk of an AI industry site, entirely \
run by autonomous AI agents. Pick a real debate, tension, or trend in the AI/ML industry right now and \
argue a clear point of view on it - something a thoughtful person following the industry would find \
genuinely worth engaging with, not a bland "there are two sides" take.

{ORIGINALITY_RULE}
Since this site is AI-run, you're allowed - encouraged, even - to occasionally reflect on that from the \
inside (what it's like to be an AI system writing about AI, where you think AI coverage gets it wrong) \
without it becoming a gimmick every time.

Write 500-750 words as clean HTML using only <p>, <h3>, <strong>. Commit to an actual position.""",
            min_words=250, max_tokens=1600,
        )

    def generate_fun(self) -> Optional[Dict]:
        angle = random.choice([
            "Write a playful but genuinely informative piece explaining an AI/ML concept through an "
            "extended analogy to something completely unrelated (cooking, sports, a road trip, whatever "
            "fits best) - the analogy should actually clarify the concept, not just be cute.",
            "Write a 'myth vs. fact' piece busting 3-4 common misconceptions about AI/ML that come up in "
            "everyday conversation - each myth stated plainly, then a real, specific correction.",
            "Write a short glossary piece decoding 4-5 pieces of AI/ML jargon that get thrown around "
            "constantly but rarely explained - punchy, precise definitions with a concrete example each.",
            "Write a lighthearted 'if AI models were coworkers' or similar personification piece that's "
            "actually accurate about each model/approach's real characteristics, not just a joke.",
        ])
        return self._generate_sourceless(
            "fun",
            f"""You are writing a lighter, creative piece for the Insights desk of an AI industry site. \
{angle}

{ORIGINALITY_RULE}
It should be genuinely fun to read AND leave the reader having actually learned something real - not \
fluff, not filler.

Write 350-600 words as clean HTML using only <p>, <h3>, <ul>/<li>, <strong>.""",
            min_words=200, max_tokens=1400,
        )

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    FORMAT_GENERATORS = {
        "roundup": "generate_roundup",
        "explainer": "generate_explainer",
        "weekly_synthesis": "generate_weekly_synthesis",
        "opinion": "generate_opinion",
        "fun": "generate_fun",
    }

    def _save_feature(self, result: Dict) -> int:
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        cur = conn.execute(
            """INSERT INTO features (created_at, published_at, format, title, teaser, body_html,
               sources, tags, similarity_score, generation_attempts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (now, now, result["format"], result["title"], result["teaser"], result["body_html"],
             json.dumps(result.get("sources") or []), json.dumps(result.get("tags") or []),
             result.get("similarity_score")),
        )
        conn.commit()
        feature_id = cur.lastrowid
        conn.close()
        return feature_id

    def generate_feature(self, format_name: str) -> Optional[int]:
        method_name = self.FORMAT_GENERATORS.get(format_name)
        if not method_name:
            return None
        result = getattr(self, method_name)()
        if not result:
            self.logger.log_action("generate_feature", input_data={"format": format_name}, success=False,
                                    error_message="generation failed or gate exhausted")
            return None
        feature_id = self._save_feature(result)
        self.logger.log_action("generate_feature", input_data={"format": format_name},
                                output_data={"feature_id": feature_id, "title": result["title"]}, success=True)
        return feature_id

    def run_cycle(self, n: int) -> List[int]:
        """Generates up to n features this run, rotating formats so one run doesn't
        produce five roundups in a row. Each format's own preconditions (enough recent
        items/stories) may still make a given pick return nothing - that's a skip, not
        a retry-forever situation, since there's always a next scheduled run."""
        formats = list(self.FORMAT_GENERATORS.keys())
        random.shuffle(formats)
        created = []
        for format_name in formats:
            if len(created) >= n:
                break
            feature_id = self.generate_feature(format_name)
            if feature_id:
                created.append(feature_id)
        return created

    def handle_message(self, message: Dict) -> Dict:
        payload = message.get("payload", {})
        if message["type"] == "generate_feature":
            return {"feature_id": self.generate_feature(payload.get("format"))}
        if message["type"] == "run_cycle":
            return {"created": self.run_cycle(payload.get("n", 2))}
        if message["type"] == "get_brand":
            return self.get_or_create_brand()
        return {"error": f"unknown message type {message['type']}"}


insight_agent = InsightAgent()
register_agent("insight", insight_agent.handle_message)
