"""
Stage 2: Dedup / Cluster.

v1 used TF-IDF word-overlap clustering. Tested against real output, it failed
in both directions: it merged unrelated stories that happened to share
boilerplate vocabulary (e.g. two OpenAI stories, or two "AI safety" stories),
and it FAILED to merge genuinely related stories that used different wording
(e.g. "OpenAI-Apple partnership announced" vs "OpenAI responds to Apple
lawsuit" - same story, near-zero word overlap). That's a ceiling on what
word-matching can do, not a threshold-tuning problem.

v2 has an LLM do the grouping directly. It's one extra call per run (cheap - this
runs once per digest, not per article or per subscriber), and it understands
semantic/topical relationships that word overlap can't.

Routed through Agent.call_llm (Claude -> Groq -> Gemini) rather than a raw Claude
client: this used to be a single point of failure with no fallback at all -
if Claude was down, clustering silently degraded to "every article is its own
cluster" even when Groq/Gemini were perfectly healthy.
"""
import json
from datetime import datetime, timedelta, timezone

from config import LOOKBACK_HOURS
from db import get_connection
from agents.base_agent import Agent

_agent = Agent("Clusterer")

CLUSTER_PROMPT = """Below is a numbered list of article headlines and snippets from \
the last {hours} hours of AI news. Group them into stories: articles that cover the \
SAME underlying event, announcement, or development go in the same group. Articles on \
different topics - even from the same company, even using similar generic AI \
vocabulary - must stay in separate groups. When in doubt, keep them separate; false \
splits are far less costly than false merges.

Articles:
{articles_block}

Respond ONLY with valid JSON, no other text, in this exact format:
{{"groups": [[0, 3], [1], [2, 5, 7]]}}

Every article index (0 to {max_idx}) must appear in exactly one group.
"""

# Keep prompt size sane - if you're pulling from many high-volume feeds,
# raise this only after checking your typical daily article count.
MAX_ARTICLES_PER_CLUSTER_CALL = 150


def build_articles_block(rows):
    lines = []
    for i, r in enumerate(rows):
        snippet = (r["summary_raw"] or "")[:200].replace("\n", " ")
        lines.append(f'{i}. [{r["source"]}] {r["title"]} — {snippet}')
    return "\n".join(lines)


def cluster_articles():
    conn = get_connection()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).isoformat()
    
    print(f"Clustering articles from: {cutoff}")
    print(f"Current UTC time: {datetime.now(timezone.utc).isoformat()}")

    # CRITICAL: Exclude articles from already-sent clusters
    # This prevents duplicate content across pipeline runs (Task 1.4)
    rows = conn.execute(
        """SELECT a.id, a.source, a.title, a.summary_raw, a.published_at 
           FROM articles a
           LEFT JOIN clusters c ON a.cluster_id = c.id
           WHERE a.cluster_id IS NULL 
             AND (a.published_at >= ? OR a.published_at IS NULL)
             AND (c.sent_at IS NULL OR c.sent_at IS NULL)
           ORDER BY a.published_at DESC""",
        (cutoff,),
    ).fetchall()
    
    # Log filtering stats
    total_unclustered = conn.execute(
        """SELECT COUNT(*) as count FROM articles WHERE cluster_id IS NULL"""
    ).fetchone()['count']
    
    filtered_count = total_unclustered - len(rows)
    if filtered_count > 0:
        print(f"✓ Filtered out {filtered_count} articles from sent clusters (duplicate prevention)")

    if not rows:
        print("Cluster: no new articles to cluster.")
        conn.close()
        return 0

    print(f"Found {len(rows)} unclustered articles within lookback window.")
    
    # Debug: show date range of articles
    if rows:
        published_dates = [r["published_at"][:10] if r["published_at"] else "unknown" for r in rows]
        print(f"Article published dates range: {min(published_dates)} to {max(published_dates)}")

    if len(rows) > MAX_ARTICLES_PER_CLUSTER_CALL:
        print(f"  [warn] {len(rows)} articles is a lot for one grouping call - "
              f"truncating to first {MAX_ARTICLES_PER_CLUSTER_CALL}. Consider running "
              f"more often or raising MAX_ARTICLES_PER_CLUSTER_CALL.")
        rows = rows[:MAX_ARTICLES_PER_CLUSTER_CALL]

    ids = [r["id"] for r in rows]
    n = len(ids)

    if n == 1:
        groups = [[0]]
    else:
        prompt = CLUSTER_PROMPT.format(
            hours=LOOKBACK_HOURS,
            articles_block=build_articles_block(rows),
            max_idx=n - 1,
        )
        try:
            text = _agent.call_llm(prompt, max_tokens=2000, json_mode=True)
            if not text:
                raise RuntimeError("all LLM providers failed or circuit open")
            parsed = json.loads(text)
            groups = parsed["groups"]

            # Safety net: make sure every index appears exactly once. If the
            # model missed any, give each a singleton group rather than
            # silently dropping articles from the digest.
            seen = set()
            for g in groups:
                seen.update(g)
            missing = set(range(n)) - seen
            for m in missing:
                groups.append([m])

        except Exception as e:
            print(f"  [error] clustering call failed, falling back to no grouping: {e}")
            groups = [[i] for i in range(n)]

    cluster_count = 0
    for group_indices in groups:
        cur = conn.execute(
            "INSERT INTO clusters (created_at) VALUES (?)",
            (datetime.now(timezone.utc).isoformat(),),
        )
        cluster_id = cur.lastrowid
        article_ids = [ids[k] for k in group_indices if 0 <= k < n]
        if not article_ids:
            continue
        conn.executemany(
            "UPDATE articles SET cluster_id = ? WHERE id = ?",
            [(cluster_id, aid) for aid in article_ids],
        )
        cluster_count += 1

    conn.commit()
    conn.close()
    print(f"Cluster done: {n} articles grouped into {cluster_count} clusters.")
    return cluster_count


if __name__ == "__main__":
    cluster_articles()
