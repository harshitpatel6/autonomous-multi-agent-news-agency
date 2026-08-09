"""
Staff Writer Agent: expands an already-approved, fact-checked cluster (headline +
short summary + source articles) into a full-length article for the website.

Only called for stories that already survived Reporter -> Fact-Checker -> Editor -> QA,
and only once per cluster (result is cached in clusters.full_content), so this doesn't
multiply LLM cost across the whole pipeline.
"""
from typing import Dict, List, Optional

from agents.base_agent import Agent
from agents.message_router import register_agent

ARTICLE_PROMPT_TEMPLATE = """You are a staff writer at a professional AI industry news site (think \
the editorial quality of TechCrunch or Inc42). You've been given an already fact-checked story to \
write up in full for the website. Do not invent facts, quotes, or numbers that aren't in the sources \
below — only elaborate on, contextualize, and explain what's actually there.

HEADLINE: {headline}
CATEGORY: {category}
EDITORIAL BRIEF (already-approved short summary): {summary}

SOURCE ARTICLES:
{sources_block}

Write a full article, 450-650 words, in clean HTML using only <p>, <h3>, <ul>/<li>, and <strong> tags \
(no <html>/<body>/inline styles/markdown). Structure:
1. A strong lede paragraph (2-3 sentences) that leads with what actually happened.
2. A "Why it matters" <h3> section: the practical or strategic implication for someone who builds with \
or invests in AI.
3. A "The details" <h3> section: the concrete specifics — names, numbers, dates, what changed technically \
or commercially. If sources disagree on a fact or framing, say so plainly instead of picking a side silently.
4. A short closing paragraph on what to watch next, grounded only in what the sources imply, not speculation \
you're inventing.

Tone: confident, plain-language, no hype words ("game-changing", "revolutionary"), no filler ("in conclusion", \
"it remains to be seen"). Write like a human editor who has read every source, not like a summary of summaries.

Respond ONLY with valid JSON, no other text: {{"full_content": "<p>...</p>..."}}
"""


class WriterAgent(Agent):
    """Expands approved clusters into full website articles."""

    def __init__(self):
        super().__init__("Writer")

    @staticmethod
    def _build_sources_block(articles: List[Dict]) -> str:
        lines = []
        for a in articles:
            snippet = (a.get("summary_raw") or "")[:800]
            lines.append(f"- [{a['source']}] {a['title']}\n  {snippet}")
        return "\n".join(lines)

    def write_full_article(self, headline: str, category: str, summary: str, articles: List[Dict]) -> Optional[str]:
        if not articles:
            return None
        prompt = ARTICLE_PROMPT_TEMPLATE.format(
            headline=headline,
            category=category or "General",
            summary=summary,
            sources_block=self._build_sources_block(articles),
        )
        response = self.call_llm(prompt, max_tokens=1400, json_mode=True)
        parsed = self.parse_json(response)
        success = bool(parsed and parsed.get("full_content"))
        self.logger.log_action(
            "write_full_article", input_data={"headline": headline},
            output_data={"chars": len(parsed["full_content"])} if success else None,
            success=success,
        )
        return parsed["full_content"] if success else None

    def handle_message(self, message: Dict) -> Dict:
        payload = message.get("payload", {})
        if message["type"] == "write_full_article":
            result = self.write_full_article(
                payload.get("headline"), payload.get("category"),
                payload.get("summary"), payload.get("articles", []),
            )
            return {"result": result}
        return {"error": f"unknown message type {message['type']}"}


writer_agent = WriterAgent()
register_agent("writer", writer_agent.handle_message)
