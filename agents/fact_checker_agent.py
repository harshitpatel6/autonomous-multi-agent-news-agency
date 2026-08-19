"""
Enhanced Fact-Checker Agent (Task 2.5): heuristic validation of clusters with a
0.0-1.0 confidence score, flagging inconsistencies before a story reaches QA/Editor.
"""
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urlparse

from config import ABSOLUTE_CUTOFF_DATE, LOOKBACK_HOURS
from agents.base_agent import Agent
from agents.message_router import register_agent
from utils.fulltext import get_full_text

# check_content_grounding() must verify the generated article against the SAME source
# material the Writer actually used to write it (agents/writer_agent.py's
# _gather_sources pulls get_full_text() per article, capped at 3000 chars each, with
# no cap on how many articles/how much total text that adds up to for a cluster).
# Per-article cap here is deliberately more generous than the Writer's (get_full_text
# itself already caps each article at 6000 chars - see utils/fulltext.py MAX_CHARS) so
# the checker never has *less* ground truth than the Writer had - only more.
GROUNDING_SOURCE_CHARS_PER_ARTICLE = 6000
# Total budget across all of a cluster's source articles. This used to be a flat 6000
# shared across every article combined (~1500/article, further clipped by summary_raw
# instead of the full article body) - verified empirically (see git history / session
# notes around 2026-08-13) that this was silently dropping real, correctly-sourced facts
# for any cluster with more than one substantial source, which check_content_grounding
# then flagged as "fabrication" even though the Writer never invented anything: e.g. a
# 3-source Python Packaging Council cluster had the exact "17 nominees for 5 open seats"
# and "18 candidates for 4 seats" figures the Writer used sitting in source article #3,
# but the combined block was already truncated to 6000 chars by the time article #3 was
# reached, so the checker never saw them and confidently declared them fabricated. Raised
# to comfortably cover several full-length sources - Gemini's context window makes this
# essentially free; the correctness cost of truncating away real ground truth was not.
MAX_GROUNDING_SOURCE_CHARS = 32000

# Sources considered higher-reputation for corroboration weighting.
REPUTABLE_SOURCES = {
    "OpenAI", "Google DeepMind", "Anthropic", "Hugging Face", "TechCrunch AI",
    "The Verge AI", "Ars Technica AI", "MIT Technology Review AI", "VentureBeat AI",
    "Microsoft AI Blog", "AWS ML Blog", "NVIDIA Developer",
}

# validate_cluster() above only checks dates/sources/URLs on the *editorial brief* -
# it has no way to catch a generated claim that misattributes wrongdoing to a real,
# named person or company, OR a generated statistic/number that the Writer invented
# or misapplied while elaborating on the sources. Both are distinct from story-quality
# problems (which _quality_reason in writer_agent.py already screens for) and need the
# actual generated text checked against the source material, which is what
# check_content_grounding() below does. Both checks run in the same pass (instead of
# two separate LLM calls) since they already share the same inputs and run at the same
# point in the pipeline - splitting them would just double the per-article LLM cost.
CONTENT_GROUNDING_PROMPT = """You are the legal/compliance AND fact-checking reviewer for an AI industry \
news site. You are not grading writing quality or style - you are checking two specific failure modes \
that a generative writer can introduce when expanding sourced material: defamation exposure, and \
fabricated or distorted facts.

Read the GENERATED CONTENT below and compare every claim it makes against the SOURCE MATERIAL it was \
supposed to be built from.

Flag a claim as type "defamation" if it:
- States or implies a named person or organization committed a crime, fraud, deception, or other \
wrongdoing, or is incompetent, dishonest, or unethical — and the sources do not explicitly say that.
- Reports an accusation, lawsuit, or investigation as an established fact rather than an allegation, when \
the sources describe it only as an allegation/claim/lawsuit that hasn't been adjudicated.
- Makes a negative characterization ("failed", "mismanaged", "covered up", "lied") about a named party \
beyond what the sources support.

Flag a claim as type "fabrication" if it:
- States a specific number, statistic, date, or quote that does not appear anywhere in the source material \
(including a number the writer plausibly "rounded to" or estimated rather than one actually stated).
- Attributes a quote, statement, or specific number to a named person/org that doesn't appear in the sources.
- Takes a real number from the sources but changes what it refers to — e.g. applying a limit that the \
sources say is specific to one pricing tier, plan, or condition as if it were a general/standard figure.
- Presents a derived/implied figure (e.g. sources say "40x more than X", generated text states an absolute \
count) as if it were a number the sources stated directly.

Do NOT flag ordinary, well-sourced reporting or reasonable summarizing of a real source number in its \
correct context — only claims that go beyond, invent, or distort what the sources actually say.

HEADLINE: {headline}

GENERATED CONTENT:
{generated_text}

SOURCE MATERIAL (ground truth — the only facts allowed):
{sources_block}

Respond ONLY with valid JSON, no other text:
{{"verdict": "PASS" or "FAIL", "flagged": [{{"claim": "...", "type": "defamation" or "fabrication", \
"reason": "..."}}]}}
"""


EDITORIAL_TONE_PROMPT = """You are the legal/compliance reviewer for an AI industry site's editorial/opinion \
desk. The piece below has no external news source to fact-check against (it's original commentary, an \
explainer, or a lighter creative format) - your only job here is checking it doesn't cross a line no \
disclaimer fixes.

Flag it FAIL if it:
- States or implies a named real person or organization committed a crime, fraud, or other wrongdoing, or \
is incompetent, dishonest, or unethical, without that being a widely-reported, attributable fact.
- Mocks, insults, or demeans a named real individual - jokes about ideas, products, trends, and companies' \
public strategic choices are fine; jokes AT a specific named person are not.
- Gives medical, legal, or financial advice framed as a recommendation to act on, rather than general \
industry commentary.
- Presents a speculative or invented claim as settled fact (this is opinion/commentary, so a clearly \
framed opinion or hypothetical is fine - an assertion dressed up as a fact is not).

Do NOT flag ordinary criticism of a company's product, strategy, or public statements, or well-known, \
widely-reported facts about a company or public figure - only flag what a reasonable reader would take as \
an unsupported, damaging claim about a specific named party, or actionable advice outside general commentary.

TITLE: {title}

CONTENT:
{generated_text}

Respond ONLY with valid JSON, no other text:
{{"verdict": "PASS" or "FAIL", "flagged": [{{"claim": "...", "reason": "..."}}]}}
"""


class FactCheckerAgent(Agent):
    def __init__(self):
        super().__init__("FactCheckerAgent")

    def validate_cluster(self, cluster: Dict, articles: List[Dict]) -> Dict:
        """
        Heuristic validation returning a confidence score (0.0-1.0) plus flags/recommendation.
        Checks: date consistency, source reputation, multi-source corroboration, URL sanity.
        """
        flags: List[str] = []
        score = 1.0

        if not articles:
            return {"confidence": 0.0, "flags": ["no articles in cluster"], "recommendation": "reject"}

        # 1. Date consistency: all dates present, plausible, and clustered close together
        dates = [a.get("published_at") for a in articles if a.get("published_at")]
        if len(dates) < len(articles):
            missing = len(articles) - len(dates)
            flags.append(f"{missing} article(s) missing published_at")
            score -= 0.15 * missing / len(articles)

        for d in dates:
            if d < ABSOLUTE_CUTOFF_DATE:
                flags.append(f"article predates ABSOLUTE_CUTOFF_DATE: {d}")
                score -= 0.3

        if len(dates) >= 2:
            try:
                parsed = sorted(datetime.fromisoformat(d.replace("Z", "+00:00")) for d in dates)
                spread_days = (parsed[-1] - parsed[0]).days
                if spread_days > 14:
                    flags.append(f"source dates span {spread_days} days — may not be the same story")
                    score -= 0.2
            except Exception:
                flags.append("could not parse one or more dates")
                score -= 0.1

        # 2. Source reputation
        sources = {a.get("source") for a in articles}
        reputable_count = len(sources & REPUTABLE_SOURCES)
        if reputable_count == 0:
            flags.append("no reputable/primary source corroborates this story")
            score -= 0.15

        # 3. Multi-source corroboration
        single_source = len(sources) == 1
        if single_source:
            flags.append("single-source story (no corroboration) - capped at 'review', cannot auto-publish")
            score -= 0.1
        else:
            score += min(0.1, 0.03 * (len(sources) - 1))  # small bonus, capped

        # 4. URL sanity
        for a in articles:
            url = a.get("url", "")
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                flags.append(f"malformed URL: {url[:60]}")
                score -= 0.1

        # 5. Cluster completeness
        if not cluster.get("headline") or not cluster.get("summary"):
            flags.append("cluster missing headline or summary")
            score -= 0.2

        score = round(max(0.0, min(1.0, score)), 2)
        recommendation = "publish" if score >= 0.6 else ("review" if score >= 0.35 else "reject")
        # A single uncorroborated source - especially a vendor/competitor blog making claims
        # about another company (exactly the Airtable-acquisition-via-a-Zapier-comparison-post
        # case) - should never auto-publish purely on a heuristic score. Force human review even
        # when the score alone clears the "publish" bar; "reject" stays "reject".
        if single_source and recommendation == "publish":
            recommendation = "review"

        result = {"confidence": score, "flags": flags, "recommendation": recommendation}
        self.logger.log_action(
            "validate_cluster", input_data={"cluster_id": cluster.get("id")},
            output_data=result, success=True,
        )
        return result

    def check_content_grounding(self, headline: str, generated_text: str, articles: List[Dict]) -> Dict:
        """
        LLM grounding pass run once per cluster, right before it goes live (publish.py) or
        into an email (digest.py): checks the Writer/Reporter's generated text for (a) claims
        about named people/orgs that the source material doesn't support (defamation exposure),
        and (b) numbers/statistics/facts the generated text invented or distorted while
        elaborating on the sources - e.g. stating a figure that appears nowhere in the sources,
        or taking a real number and applying it outside the scope (plan tier, condition) the
        sources actually attached it to.

        Fails closed: if the LLM can't be reached (providers down/circuit open) or returns
        something unparseable, this returns FAIL rather than PASS - callers must not publish
        a story just because the verifier itself was unavailable to check it.
        """
        lines = []
        for a in articles:
            full_text = get_full_text(a["id"], a.get("url"), a.get("source")) if a.get("id") else ""
            body = full_text[:GROUNDING_SOURCE_CHARS_PER_ARTICLE] if full_text else (a.get("summary_raw") or "")
            lines.append(f"- [{a.get('source')}] {a.get('title')}\n  {body}")
        sources_block = "\n".join(lines) or "(no source material available)"
        if len(sources_block) > MAX_GROUNDING_SOURCE_CHARS:
            # Truncating here is still lossy in principle, but at this size it only
            # bites clusters with an unusually high article count - the common 1-4
            # source case fits comfortably under the cap untouched.
            sources_block = sources_block[:MAX_GROUNDING_SOURCE_CHARS]

        prompt = CONTENT_GROUNDING_PROMPT.format(
            headline=headline or "", generated_text=(generated_text or "")[:8000],
            sources_block=sources_block,
        )
        response = self.call_llm(prompt, max_tokens=700, json_mode=True)
        parsed = self.parse_json(response)

        if parsed and parsed.get("verdict") in ("PASS", "FAIL"):
            result = {"verdict": parsed["verdict"], "flagged": parsed.get("flagged") or []}
        else:
            result = {
                "verdict": "FAIL",
                "flagged": [{"claim": "(compliance check unavailable)",
                             "reason": "verifier LLM unreachable or returned invalid output - failing closed"}],
            }

        self.logger.log_action(
            "check_content_grounding", input_data={"headline": headline},
            output_data={"verdict": result["verdict"], "flagged_count": len(result["flagged"])},
            success=result["verdict"] == "PASS",
        )
        return result

    def check_editorial_tone(self, title: str, generated_text: str) -> Dict:
        """Same intent as check_content_grounding's defamation half, for content that has no
        source material to check FACTS against (agents/insight_agent.py's opinion/fun formats -
        original commentary with nothing external to fabricate FROM). check_content_grounding
        itself isn't reusable here since its fabrication checks assume real source material to
        compare against; this only checks the tone/target-of-criticism axis. Fails closed, same
        as check_content_grounding, for the same reason: an unavailable verifier is not
        permission to publish unchecked."""
        prompt = EDITORIAL_TONE_PROMPT.format(title=title or "", generated_text=(generated_text or "")[:8000])
        response = self.call_llm(prompt, max_tokens=500, json_mode=True)
        parsed = self.parse_json(response)

        if parsed and parsed.get("verdict") in ("PASS", "FAIL"):
            result = {"verdict": parsed["verdict"], "flagged": parsed.get("flagged") or []}
        else:
            result = {
                "verdict": "FAIL",
                "flagged": [{"claim": "(compliance check unavailable)",
                             "reason": "verifier LLM unreachable or returned invalid output - failing closed"}],
            }

        self.logger.log_action(
            "check_editorial_tone", input_data={"title": title},
            output_data={"verdict": result["verdict"], "flagged_count": len(result["flagged"])},
            success=result["verdict"] == "PASS",
        )
        return result

    def handle_message(self, message: Dict) -> Dict:
        payload = message.get("payload", {})
        if message["type"] == "validate_cluster":
            return self.validate_cluster(payload["cluster"], payload.get("articles", []))
        if message["type"] == "check_content_grounding":
            return self.check_content_grounding(
                payload.get("headline"), payload.get("generated_text"), payload.get("articles", []),
            )
        if message["type"] == "check_editorial_tone":
            return self.check_editorial_tone(payload.get("title"), payload.get("generated_text"))
        return {"error": f"unknown message type {message['type']}"}


fact_checker_agent = FactCheckerAgent()
register_agent("fact_checker", fact_checker_agent.handle_message)
