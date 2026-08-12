"""
Beat-based Reporter Agents (Task 2.4): specialized summarization per news beat.
Each reporter uses a beat-specific prompt so the tone/focus matches the story type.
"""
import json
from typing import Dict, List, Optional

from utils.fulltext import get_full_text
from agents.base_agent import Agent
from agents.message_router import register_agent

BASE_PROMPT_TEMPLATE = """You are the {beat_name} Reporter at a professional AI industry newsletter — an \
experienced beat reporter, not a summarization tool. Below are one or more articles covering what may be \
the same underlying story, from different sources. Sources marked (FULL TEXT) are the actual article body; \
sources marked (TEASER ONLY) are just a short RSS blurb, so lean on the FULL TEXT sources for specifics \
when both are present.

LEGAL/DEFAMATION RULE: never state or imply that a specific, named person or organization committed a \
crime, fraud, or other wrongdoing, or is incompetent, dishonest, or unethical, unless the sources say so \
explicitly. Report accusations, lawsuits, or investigations as exactly that — attributed to whoever is \
making the claim — never as settled fact. When unsure, omit the characterization rather than risk it.

{beat_focus}

Sources:
{sources_block}

Do four things:
1. Write a short, punchy HEADLINE (5-8 words max, no generic phrases like "introduces" or "announces")
2. Categorize this story into ONE of these sections:
   - Company News — product launches, partnerships, acquisitions, leadership moves from established AI companies
   - Business & Enterprise AI — companies adopting/selling AI as a product (SaaS AI, enterprise tools), new AI \
tools or devices launched commercially
   - Funding & Investment — funding rounds, valuations, M&A, IPOs involving AI companies/startups
   - Startup Launches — a new AI-related startup or its first product launching/coming out of stealth
   - Research & Models — new models, papers, benchmarks, technical breakthroughs
   - Tools & Engineering — libraries, frameworks, developer tools, infra releases
   - Policy & Regulation — government policy, regulation, legal rulings affecting AI
   - Other — anything that doesn't fit the above
   If a story could fit more than one (e.g. a startup announcing a funding round), pick the most specific: a \
new company/product launching is Startup Launches even if it also raised money; a funding round for an \
already-established company is Funding & Investment.
3. Write a well-reported SUMMARY (4-6 sentences). Lead with the single most important concrete fact — not a \
throat-clearing setup sentence. Pull out every specific name, number, and example the sources give you (if a \
source lists multiple companies/deals/products, name them, don't collapse them into "various" or "several"). \
Then, in your own words as a reporter who gets why this matters, say what it actually means for someone \
building with AI — not a generic "this is significant because..." line, but a specific claim. If sources \
disagree on a fact or framing, name the discrepancy in one clause. Never speculate beyond what the sources \
say, and never write a sentence announcing that a detail is missing ("specific details are not provided," \
"it remains unclear whether...") — if you don't have it, just don't mention it. No hype words \
("game-changing", "revolutionary"), no filler ("in conclusion", "it remains to be seen").
4. Score how important this story is for someone who builds with AI day to day, from 1 (minor/noise) to 10 \
(major development). Consider novelty and practical impact, not just how many outlets covered it.

Respond ONLY with valid JSON, no other text:
{{"headline": "...", "category": "...", "summary": "...", "importance_score": N}}
"""


class ReporterAgent(Agent):
    """Base reporter. Subclass and set beat_name/beat_focus/categories to specialize."""

    beat_name = "General"
    beat_focus = "Cover the story neutrally and factually."
    categories: List[str] = []  # categories this reporter claims; empty = catch-all

    def __init__(self):
        super().__init__(f"Reporter[{self.beat_name}]")

    def handles_category(self, category: Optional[str]) -> bool:
        return not self.categories or category in self.categories

    @staticmethod
    def _build_sources_block(articles: List[Dict]) -> str:
        lines = []
        for a in articles:
            full_text = get_full_text(a["id"], a.get("url"), a.get("source")) if a.get("id") else ""
            if full_text:
                lines.append(f"- [{a['source']}] {a['title']} (FULL TEXT)\n  {full_text[:2000]}")
            else:
                snippet = (a.get("summary_raw") or "")[:500]
                lines.append(f"- [{a['source']}] {a['title']} (TEASER ONLY)\n  {snippet}")
        return "\n".join(lines)

    def summarize_cluster(self, articles: List[Dict]) -> Optional[Dict]:
        """Summarize a cluster of articles with this reporter's beat-specific lens."""
        if not articles:
            return None
        prompt = BASE_PROMPT_TEMPLATE.format(
            beat_name=self.beat_name,
            beat_focus=self.beat_focus,
            sources_block=self._build_sources_block(articles),
        )
        response = self.call_llm(prompt, max_tokens=700, json_mode=True)
        parsed = self.parse_json(response)
        success = bool(parsed and "headline" in parsed and "importance_score" in parsed)
        self.logger.log_action(
            "summarize_cluster", input_data={"n_articles": len(articles)},
            output_data={"headline": parsed.get("headline")} if parsed else None,
            success=success,
        )
        if not success:
            return None
        try:
            parsed["importance_score"] = int(parsed["importance_score"])
        except (TypeError, ValueError):
            parsed["importance_score"] = 5
        return parsed

    def handle_message(self, message: Dict) -> Dict:
        payload = message.get("payload", {})
        if message["type"] == "summarize_cluster":
            return {"result": self.summarize_cluster(payload.get("articles", []))}
        return {"error": f"unknown message type {message['type']}"}


class CompanyNewsReporter(ReporterAgent):
    beat_name = "Company News"
    beat_focus = "Focus on: product launches, partnerships, acquisitions, leadership changes, and business strategy. Be skeptical of PR framing."
    categories = ["Company News", "Business & Enterprise AI"]


class ResearchReporter(ReporterAgent):
    beat_name = "Research"
    beat_focus = "Focus on: new models, papers, benchmarks, and technical breakthroughs. Explain WHY it matters technically, not just what was announced."
    categories = ["Research & Models"]


class ToolsReporter(ReporterAgent):
    beat_name = "Tools & Engineering"
    beat_focus = "Focus on: libraries, frameworks, developer tools, and infra releases. Call out breaking changes and practical adoption impact for engineers."
    categories = ["Tools & Engineering"]


class GeneralReporter(ReporterAgent):
    beat_name = "General"
    beat_focus = "Cover policy, regulation, or any story that doesn't fit a specialist beat."
    categories = []  # catch-all


REPORTER_POOL: List[ReporterAgent] = [
    CompanyNewsReporter(), ResearchReporter(), ToolsReporter(), GeneralReporter(),
]

for _r in REPORTER_POOL:
    register_agent(f"reporter:{_r.beat_name}", _r.handle_message)


def get_reporter_for_category(category: Optional[str]) -> ReporterAgent:
    """Route a cluster to the specialist reporter for its category, falling back to General."""
    for reporter in REPORTER_POOL:
        if reporter.categories and reporter.handles_category(category):
            return reporter
    return REPORTER_POOL[-1]  # GeneralReporter catch-all


def summarize_cluster_with_beat_reporter(articles: List[Dict], hint_category: Optional[str] = None) -> Optional[Dict]:
    """
    Convenience entrypoint for summarize.py: picks a reporter (using a category hint if
    available, otherwise General) and summarizes. The reporter's own output category is
    authoritative once returned.
    """
    reporter = get_reporter_for_category(hint_category)
    return reporter.summarize_cluster(articles)
