"""
Stage 3: Summarize + rank.
For each new cluster, sends all its source articles to Claude in one call
and asks for: a synthesized 2-3 sentence summary, and an importance score.
This is the one stage worth spending on a strong model - low call volume
(one per story/day, not per subscriber), high value (it's your actual product).
"""
import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from db import get_connection

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

PROMPT_TEMPLATE = """You are an editor for a daily AI industry newsletter. Below are \
one or more articles that a similarity algorithm grouped as possibly the same story.

Sources:
{sources_block}

First, check: are these articles ACTUALLY about the same underlying event or \
announcement, or did they just get grouped because they share generic AI vocabulary? \
Be honest about this - grouping errors happen.

Then do three things:
1. Write ONE short, specific headline (under 12 words, no clickbait, plain description
   of what happened).
2. Write ONE synthesized summary (2-3 sentences, plain language, no hype) covering
   what's actually new. Only mention that "sources differ" if there's a genuine factual
   or framing disagreement - don't manufacture a disagreement out of articles that are
   simply about different topics from the same company.
3. Score how important this is for someone who builds with AI day to day, from 1
   (minor/noise) to 10 (major development). If the articles turned out to be unrelated
   topics incorrectly grouped together, score it 1 and say so plainly in the summary
   instead of trying to force a synthesis.

Respond ONLY with valid JSON, no other text, in this exact format:
{{"headline": "...", "summary": "...", "importance_score": N}}
"""


def build_sources_block(articles):
    lines = []
    for a in articles:
        snippet = (a["summary_raw"] or "")[:500]
        lines.append(f'- [{a["source"]}] {a["title"]}\n  {snippet}')
    return "\n".join(lines)


def summarize_clusters():
    conn = get_connection()
    clusters = conn.execute(
        "SELECT id FROM clusters WHERE summary IS NULL"
    ).fetchall()

    if not clusters:
        print("Summarize: no new clusters to summarize.")
        conn.close()
        return 0

    done = 0
    for c in clusters:
        cluster_id = c["id"]
        articles = conn.execute(
            "SELECT source, title, summary_raw FROM articles WHERE cluster_id = ?",
            (cluster_id,),
        ).fetchall()
        if not articles:
            continue

        prompt = PROMPT_TEMPLATE.format(sources_block=build_sources_block(articles))

        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            # strip accidental code fences
            text = text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(text)

            conn.execute(
                "UPDATE clusters SET headline = ?, summary = ?, importance_score = ? WHERE id = ?",
                (parsed["headline"], parsed["summary"], int(parsed["importance_score"]), cluster_id),
            )
            conn.commit()
            done += 1
        except Exception as e:
            print(f"  [error] cluster {cluster_id}: {e}")

    conn.close()
    print(f"Summarize done: {done} clusters summarized.")
    return done


if __name__ == "__main__":
    summarize_clusters()