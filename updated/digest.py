"""
Stage 4: Build digest.
Pulls top-scored, not-yet-sent clusters and renders a clean HTML email.
"""
from datetime import date
from config import TOP_N_STORIES, MIN_IMPORTANCE_SCORE
from db import get_connection

HTML_WRAPPER = """\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, Helvetica, Arial, sans-serif; max-width: 640px;
             margin: 0 auto; padding: 24px; color: #1a1a1a;">
  <h1 style="font-size: 22px; margin-bottom: 4px;">AI Daily &mdash; {date_str}</h1>
  <p style="color: #666; font-size: 13px; margin-top: 0;">{count} stories, synthesized from {source_count} sources</p>
  <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
  {stories_html}
  <hr style="border: none; border-top: 1px solid #eee; margin: 24px 0;">
  <p style="color: #999; font-size: 12px;">You're receiving this as a test send.</p>
</body>
</html>
"""

STORY_TEMPLATE = """\
<div style="margin-bottom: 22px;">
  <h2 style="font-size: 16px; margin-bottom: 6px;">{rank}. {headline}</h2>
  <p style="font-size: 14px; line-height: 1.5; margin: 0 0 6px 0;">{summary}</p>
  <p style="font-size: 12px; color: #888; margin: 0;">Sources: {sources}</p>
</div>
"""


def build_digest_html():
    conn = get_connection()
    clusters = conn.execute(
        """SELECT id, headline, summary, importance_score FROM clusters
           WHERE summary IS NOT NULL AND included_in_digest = 0
                 AND importance_score >= ?
           ORDER BY importance_score DESC
           LIMIT ?""",
        (MIN_IMPORTANCE_SCORE, TOP_N_STORIES),
    ).fetchall()

    if not clusters:
        conn.close()
        print("Digest: no clusters ready to send.")
        return None, []

    stories_html_parts = []
    all_source_names = set()
    cluster_ids = []

    for idx, c in enumerate(clusters, start=1):
        articles = conn.execute(
            "SELECT source, title, url FROM articles WHERE cluster_id = ?",
            (c["id"],),
        ).fetchall()
        sources_linked = ", ".join(
            f'<a href="{a["url"]}" style="color:#0066cc;">{a["source"]}</a>' for a in articles
        )
        for a in articles:
            all_source_names.add(a["source"])

        stories_html_parts.append(
            STORY_TEMPLATE.format(
                rank=idx,
                headline=c["headline"] or (articles[0]["title"] if articles else "Untitled"),
                summary=c["summary"],
                sources=sources_linked,
            )
        )
        cluster_ids.append(c["id"])

    html = HTML_WRAPPER.format(
        date_str=date.today().strftime("%B %d, %Y"),
        count=len(clusters),
        source_count=len(all_source_names),
        stories_html="\n".join(stories_html_parts),
    )

    conn.close()
    return html, cluster_ids


def mark_as_sent(cluster_ids):
    conn = get_connection()
    conn.executemany(
        "UPDATE clusters SET included_in_digest = 1 WHERE id = ?",
        [(cid,) for cid in cluster_ids],
    )
    conn.commit()
    conn.close()