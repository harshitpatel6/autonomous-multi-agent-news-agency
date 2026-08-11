"""
Full-article text fetching. RSS feeds only give a short teaser in summary_raw —
e.g. Inc42's feed cuts off at ~400 chars mid-sentence ("...This marks&#8230;") —
which isn't enough source material for the Writer/Reporter agents to produce real
coverage, no matter how the prompt is worded. This fetches and extracts the actual
article body from the source URL so they have something real to work from.

Best-effort: many sites will fail (paywalls, bot-blocking, timeouts, non-article
pages) and callers should fall back to summary_raw when this returns "".
"""
import trafilatura

from db import get_connection

MAX_CHARS = 6000  # bound LLM input cost; article bodies rarely need more than this
MIN_CHARS = 200    # shorter than this isn't meaningfully better than the RSS teaser


def _extract(url: str) -> str:
    if not url:
        return ""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False) or ""
        return text[:MAX_CHARS] if len(text) >= MIN_CHARS else ""
    except Exception:
        return ""


def get_full_text(article_id: int, url: str) -> str:
    """
    Cached full-text fetch for one article row: articles.full_text is NULL until the
    first attempt, then always a string ("" on failure). Caching failures too means a
    dead/blocked URL only gets tried once, not re-fetched on every summarize/write pass
    or self-healing retry cycle.
    """
    conn = get_connection()
    row = conn.execute("SELECT full_text FROM articles WHERE id = ?", (article_id,)).fetchone()
    if row and row["full_text"] is not None:
        conn.close()
        return row["full_text"]
    conn.close()

    text = _extract(url)

    conn = get_connection()
    conn.execute("UPDATE articles SET full_text = ? WHERE id = ?", (text, article_id))
    conn.commit()
    conn.close()
    return text
