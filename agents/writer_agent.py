"""
Staff Writer Agent: expands an already-approved, fact-checked cluster (headline +
short summary + source articles) into a full-length article for the website.

Only called for stories that already survived Reporter -> Fact-Checker -> Editor -> QA,
and only once per cluster (result is cached in clusters.full_content), so this doesn't
multiply LLM cost across the whole pipeline.
"""
import json
from typing import Dict, List, Optional

from db import get_connection
from utils.fulltext import get_full_text
from agents.base_agent import Agent
from agents.message_router import register_agent

ARTICLE_PROMPT_TEMPLATE = """You are a senior staff writer at a professional AI industry news site \
(think the editorial quality of TechCrunch or The Information). You've been given an already \
fact-checked story to write up in full for the website. Do not invent facts, quotes, or numbers that \
aren't in the sources below — only elaborate on, contextualize, and explain what's actually there.

HEADLINE: {headline}
CATEGORY: {category}
EDITORIAL BRIEF (already-approved short summary): {summary}

SOURCE ARTICLES (marked FULL TEXT where the actual article body was fetched, or TEASER ONLY where \
only a short RSS blurb was available):
{sources_block}

Write a full article, {word_range} words, in clean HTML using only <p>, <h3>, <ul>/<li>, and <strong> tags \
(no <html>/<body>/inline styles/markdown). Structure:
1. A strong lede paragraph (2-3 sentences) that leads with what actually happened — the single most \
important fact first, not a throat-clearing setup.
2. A "Why it matters" <h3> section: the practical or strategic implication for someone who builds with \
or invests in AI. Go beyond the obvious — cover second-order effects (competitors, pricing, ecosystem) \
where the sources support it.
3. A "The details" <h3> section: the concrete specifics — names, numbers, dates, what changed technically \
or commercially. Pull out EVERY name, figure, and fact the sources contain, not just the headline number — \
if a source lists multiple companies, deals, or examples, name them individually instead of summarizing \
them away as "various" or "several." If sources disagree on a fact or framing, say so plainly instead of \
glossing over it.
4. A "Background" <h3> section: the context a reader needs to understand why this story matters now — \
prior related moves, market position, or history, grounded only in what the sources state or clearly imply.
5. A short closing paragraph on what to watch next, grounded only in what the sources imply, not speculation \
you're inventing.

Use the full length to add depth and grounded context, not to pad with repetition or restate the same point \
in different words. If a source is TEASER ONLY and the sources collectively don't support the low end of \
{word_range} words of real substance, write what's actually supported rather than inventing filler — but \
exhaust every concrete detail across ALL sources before concluding that.

Then write KEY TAKEAWAYS: 3-5 short, standalone bullet points (each one sentence, no trailing period-less \
fragments) that a reader could scan without reading the article. Each one must carry a distinct, concrete fact \
or number from the sources — not a restatement of the editorial brief above, and not the same claim reworded \
twice. Do not write a generic "why this matters" bullet; every bullet needs a specific detail (a name, a \
number, a date, a concrete change) in it.

Voice — this is the part most AI-generated news writing gets wrong, so follow it precisely:
- Write with a point of view, like a reporter who has covered this beat for years and knows what's actually \
notable here versus routine. Don't just restate facts in order; tell the reader why this specific development \
stands out (or, if it's minor, say so instead of manufacturing false urgency).
- Never write sentences that just restate importance in the abstract — banned patterns: "this is significant \
because...", "this could indicate...", "this may reflect growing interest in...", "highlights the growing \
trend of...", "underscores the importance of...". Replace every one of those with an actual, specific claim \
about what changes for the reader.
- If the sources don't give you a detail (a dollar figure, a name, a date), do not write a sentence announcing \
that it's missing ("specific details ... are not provided," "it remains unclear whether..."). Just don't \
mention it — write confidently with what you do have instead of narrating the gaps.
- No hedge-closer paragraphs that restate the whole article in vaguer language. Every sentence should add a \
new fact or a new angle, or it shouldn't be there.
- No hype words ("game-changing", "revolutionary", "groundbreaking") and no filler ("in conclusion", "it \
remains to be seen", "only time will tell").

Respond ONLY with valid JSON, no other text: \
{{"full_content": "<p>...</p>...", "key_takeaways": ["...", "...", "..."]}}
"""


class WriterAgent(Agent):
    """Expands approved clusters into full website articles."""

    def __init__(self):
        super().__init__("Writer")

    @staticmethod
    def _build_sources_block(articles: List[Dict]) -> str:
        lines = []
        for a in articles:
            full_text = get_full_text(a["id"], a.get("url")) if a.get("id") else ""
            if full_text:
                lines.append(f"- [{a['source']}] {a['title']} (FULL TEXT)\n  {full_text[:3000]}")
            else:
                snippet = (a.get("summary_raw") or "")[:1200]
                lines.append(f"- [{a['source']}] {a['title']} (TEASER ONLY)\n  {snippet}")
        return "\n".join(lines)

    @staticmethod
    def _target_word_range(importance_score: Optional[int]) -> str:
        """Scale target article length to how big the story actually is, instead of forcing
        every cluster (a minor tools release and a major funding round alike) into the same
        800-1000 word band."""
        try:
            score = int(importance_score)
        except (TypeError, ValueError):
            return "800-1000"
        if score >= 8:
            return "1000-1200"
        if score >= 5:
            return "700-900"
        return "400-600"

    def write_full_article(
        self, headline: str, category: str, summary: str, articles: List[Dict],
        importance_score: Optional[int] = None,
    ) -> Optional[Dict]:
        """Returns {"full_content": "<html>", "key_takeaways": [...]}, or None on failure."""
        if not articles:
            return None
        prompt = ARTICLE_PROMPT_TEMPLATE.format(
            headline=headline,
            category=category or "General",
            summary=summary,
            sources_block=self._build_sources_block(articles),
            word_range=self._target_word_range(importance_score),
        )
        response = self.call_llm(prompt, max_tokens=2200, json_mode=True)
        parsed = self.parse_json(response)
        success = bool(parsed and parsed.get("full_content"))
        self.logger.log_action(
            "write_full_article", input_data={"headline": headline},
            output_data={
                "chars": len(parsed["full_content"]),
                "takeaways": len(parsed.get("key_takeaways") or []),
            } if success else None,
            success=success,
        )
        if not success:
            return None
        return {
            "full_content": parsed["full_content"],
            "key_takeaways": parsed.get("key_takeaways") or [],
        }

    def handle_message(self, message: Dict) -> Dict:
        payload = message.get("payload", {})
        if message["type"] == "write_full_article":
            result = self.write_full_article(
                payload.get("headline"), payload.get("category"),
                payload.get("summary"), payload.get("articles", []),
                payload.get("importance_score"),
            )
            return {"result": result}
        return {"error": f"unknown message type {message['type']}"}


writer_agent = WriterAgent()
register_agent("writer", writer_agent.handle_message)


def ensure_full_article(cluster: Dict) -> None:
    """
    Generate + cache a full website article (body + key takeaways) for a cluster, if it
    doesn't have both yet. Shared by digest.py (email pipeline) and publish.py (site
    pipeline) so both write through the same cache instead of duplicating this logic.

    Requiring *both* columns (not just full_content) makes this self-backfilling: articles
    published before key_takeaways existed get picked back up here (and by publish.py's
    retry_missing_full_content) and re-run through the Writer Agent, which regenerates the
    whole article in one LLM call - a one-time cost per pre-existing article.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT full_content, key_takeaways FROM clusters WHERE id = ?", (cluster["id"],)
    ).fetchone()
    if row and row["full_content"] and row["key_takeaways"]:
        conn.close()
        return

    source_articles = conn.execute(
        "SELECT id, source, title, url, summary_raw FROM articles WHERE cluster_id = ?",
        (cluster["id"],),
    ).fetchall()
    conn.close()

    if not source_articles:
        return

    try:
        result = writer_agent.write_full_article(
            cluster.get("headline"), cluster.get("category"), cluster.get("summary"),
            [dict(a) for a in source_articles], cluster.get("importance_score"),
        )
    except Exception as e:
        print(f"  [error] Writer Agent failed for cluster {cluster['id']}: {str(e)[:100]}")
        result = None

    if result:
        conn = get_connection()
        conn.execute(
            "UPDATE clusters SET full_content = ?, key_takeaways = ? WHERE id = ?",
            (result["full_content"], json.dumps(result["key_takeaways"]), cluster["id"]),
        )
        conn.commit()
        conn.close()
