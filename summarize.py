"""
Stage 3: Summarize + rank.
For each new cluster, sends all its source articles to Claude/Groq in one call
and asks for: a synthesized 2-3 sentence summary, and an importance score.
"""
import json
import time
import anthropic
from groq import Groq
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, GROQ_API_KEY, GROQ_MODEL, LLM_PROVIDER, LOOKBACK_HOURS
from db import get_connection

try:
    from agents.reporter_agent import summarize_cluster_with_beat_reporter
    REPORTERS_AVAILABLE = True
except ImportError:
    REPORTERS_AVAILABLE = False

# Initialize clients based on provider
if LLM_PROVIDER == "claude":
    claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
elif LLM_PROVIDER == "groq":
    groq_client = Groq(api_key=GROQ_API_KEY)
else:
    raise ValueError(f"Invalid LLM_PROVIDER: {LLM_PROVIDER}. Use 'claude' or 'groq'.")

# Fallback models if primary is decommissioned
GROQ_FALLBACK_MODELS = [
    GROQ_MODEL,  # Primary (from config)
    "llama-3.3-70b-versatile",  # Latest stable Llama 3.3
    "llama-3.1-8b-instant",  # Fast & lightweight
    "gemma2-9b-it",  # Alternative
]

# Rate limiting
RATE_LIMIT_DELAY = 0.5  # 500ms between requests to avoid throttling
REQUEST_TIMEOUT = 30  # 30 second timeout per request

PROMPT_TEMPLATE = """You are an editor for a daily AI industry newsletter. Below are \
multiple articles covering what may be the same underlying story, from different sources.

Sources:
{sources_block}

Do four things:
1. Write a short, punchy HEADLINE (5-8 words max, no generic phrases like "introduces" or "announces")
2. Categorize this story into ONE of these sections:
   - Company News (product launches, partnerships, acquisitions)
   - Business & Enterprise AI (companies adopting/selling AI as a product, SaaS AI, commercial AI tools/devices)
   - Funding & Investment (funding rounds, valuations, M&A, IPOs)
   - Startup Launches (a new AI startup or its first product launching/coming out of stealth)
   - Research & Models (new models, papers, benchmarks)
   - Policy & Regulation (laws, government actions, compliance)
   - Tools & Engineering (libraries, frameworks, developer tools)
   - Other (anything else)
3. Write ONE synthesized summary (2-3 sentences, plain language, no hype) that \
combines what's actually new here. If sources disagree on any fact or framing, note it briefly.
4. Score how important this story is for someone who builds with AI day to day, \
from 1 (minor/noise) to 10 (major development). Consider novelty and practical impact, \
not just how many outlets covered it.

Respond ONLY with valid JSON, no other text, in this exact format:
{{"headline": "...", "category": "...", "summary": "...", "importance_score": N}}
"""


def build_sources_block(articles):
    lines = []
    for a in articles:
        snippet = (a["summary_raw"] or "")[:500]
        lines.append(f'- [{a["source"]}] {a["title"]}\n  {snippet}')
    return "\n".join(lines)


def cleanup_old_articles():
    """Remove articles older than ABSOLUTE_CUTOFF_DATE to prevent stale content."""
    conn = get_connection()
    from config import ABSOLUTE_CUTOFF_DATE
    
    # Delete old unclustered articles (both by LOOKBACK_HOURS and ABSOLUTE_CUTOFF)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).isoformat()
    
    result1 = conn.execute(
        "DELETE FROM articles WHERE cluster_id IS NULL AND (published_at < ? OR published_at < ?)",
        (cutoff, ABSOLUTE_CUTOFF_DATE)
    )
    deleted_articles = result1.rowcount
    
    # Delete clusters with no articles (orphaned)
    result2 = conn.execute("""
        DELETE FROM clusters WHERE id NOT IN (
            SELECT DISTINCT cluster_id FROM articles WHERE cluster_id IS NOT NULL
        )
    """)
    deleted_orphaned = result2.rowcount
    
    conn.commit()
    conn.close()
    
    if deleted_articles > 0:
        print(f"✓ Cleanup: removed {deleted_articles} old articles (older than {LOOKBACK_HOURS}h or before {ABSOLUTE_CUTOFF_DATE[:10]})")
    if deleted_orphaned > 0:
        print(f"✓ Cleanup: removed {deleted_orphaned} orphaned clusters")
    
    return deleted_articles


def _summarize_one_cluster(cluster_id):
    """Fetch a cluster's articles and summarize via the beat-specific Reporter Agent (Task 2.4)."""
    conn = get_connection()
    articles = conn.execute(
        "SELECT source, title, summary_raw, published_at FROM articles WHERE cluster_id = ?",
        (cluster_id,),
    ).fetchall()
    conn.close()
    if not articles:
        return cluster_id, None
    parsed = summarize_cluster_with_beat_reporter([dict(a) for a in articles])
    return cluster_id, parsed


def _summarize_with_reporters(conn, clusters, max_workers=5):
    """Parallel summarization across beat Reporter Agents (Task 2.4)."""
    done = failed = 0
    cluster_ids = [c["id"] for c in clusters]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_summarize_one_cluster, cid): cid for cid in cluster_ids}
        for i, future in enumerate(as_completed(futures), 1):
            cluster_id = futures[future]
            try:
                _, parsed = future.result()
            except Exception as e:
                parsed = None
                print(f"  [error] cluster {cluster_id}: {str(e)[:100]}")

            if parsed:
                conn.execute(
                    "UPDATE clusters SET headline = ?, category = ?, summary = ?, importance_score = ? WHERE id = ?",
                    (parsed["headline"], parsed["category"], parsed["summary"], parsed["importance_score"], cluster_id),
                )
                conn.commit()
                done += 1
            else:
                failed += 1

            if i % 10 == 0:
                print(f"  [{i}/{len(cluster_ids)}] {done} done, {failed} failed")

    return done, failed


def summarize_clusters():
    conn = get_connection()
    
    # Get timestamp of last digest sent
    last_digest = conn.execute(
        "SELECT MAX(sent_at) as last_sent FROM digest_log"
    ).fetchone()
    last_sent_time = last_digest["last_sent"] if last_digest["last_sent"] else "2000-01-01"
    
    # CRITICAL: Query only clusters that:
    # 1. Have not been summarized yet (summary IS NULL)
    # 2. Were created after last digest
    # 3. Have NOT been sent yet (sent_at IS NULL) - Task 1.4
    clusters = conn.execute("""
        SELECT id FROM clusters 
        WHERE summary IS NULL 
          AND created_at > ?
          AND sent_at IS NULL
        ORDER BY created_at ASC
        LIMIT 50
    """, (last_sent_time,)).fetchall()
    
    # Log filtering stats
    total_unsummarized = conn.execute(
        """SELECT COUNT(*) as count FROM clusters WHERE summary IS NULL"""
    ).fetchone()['count']
    
    sent_unsummarized = conn.execute(
        """SELECT COUNT(*) as count FROM clusters 
           WHERE summary IS NULL AND sent_at IS NOT NULL"""
    ).fetchone()['count']
    
    if sent_unsummarized > 0:
        print(f"✓ Skipped {sent_unsummarized} unsummarized clusters that were already sent")

    if not clusters:
        print("Summarize: no new clusters to summarize.")
        conn.close()
        return 0

    total = len(clusters)
    done = 0
    failed = 0

    print(f"Summarize: processing {total} new clusters since {last_sent_time[:10]}...")

    if REPORTERS_AVAILABLE:
        done, failed = _summarize_with_reporters(conn, clusters)
        conn.close()
        print(f"Summarize done: {done}/{total} clusters. Failed: {failed}. (Using beat Reporter Agents)")
        return done

    for idx, c in enumerate(clusters, 1):
        cluster_id = c["id"]
        articles = conn.execute(
            "SELECT source, title, summary_raw FROM articles WHERE cluster_id = ?",
            (cluster_id,),
        ).fetchall()
        
        if not articles:
            continue

        prompt = PROMPT_TEMPLATE.format(sources_block=build_sources_block(articles))

        if LLM_PROVIDER == "claude":
            try:
                response = claude_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=400,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text.strip()
                text = text.replace("```json", "").replace("```", "").strip()
                parsed = json.loads(text)

                conn.execute(
                    "UPDATE clusters SET headline = ?, category = ?, summary = ?, importance_score = ? WHERE id = ?",
                    (parsed["headline"], parsed["category"], parsed["summary"], int(parsed["importance_score"]), cluster_id),
                )
                conn.commit()
                done += 1
                
                if idx % 10 == 0:
                    print(f"  [{idx}/{total}] {done} done, {failed} failed")
                    
            except Exception as e:
                failed += 1
                print(f"  [error] cluster {cluster_id}: {str(e)[:100]}")

        elif LLM_PROVIDER == "groq":
            success = False
            for attempt, model_name in enumerate(GROQ_FALLBACK_MODELS, 1):
                try:
                    response = groq_client.chat.completions.create(
                        model=model_name,
                        max_tokens=400,
                        messages=[{"role": "user", "content": prompt}],
                        timeout=REQUEST_TIMEOUT,
                    )
                    text = response.choices[0].message.content.strip()
                    text = text.replace("```json", "").replace("```", "").strip()
                    parsed = json.loads(text)

                    conn.execute(
                        "UPDATE clusters SET headline = ?, category = ?, summary = ?, importance_score = ? WHERE id = ?",
                        (parsed["headline"], parsed["category"], parsed["summary"], int(parsed["importance_score"]), cluster_id),
                    )
                    conn.commit()
                    done += 1
                    success = True
                    
                    if model_name != GROQ_MODEL:
                        print(f"  [info] cluster {cluster_id}: fallback model {model_name}")
                    
                    if idx % 10 == 0:
                        print(f"  [{idx}/{total}] {done} done, {failed} failed")
                    break
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    if "decommissioned" in error_msg or "not found" in error_msg:
                        # Try next model
                        continue
                    elif "timeout" in error_msg or "deadline" in error_msg:
                        # Timeout - increase delay and try again
                        time.sleep(2)
                        continue
                    elif attempt == len(GROQ_FALLBACK_MODELS):
                        # Last attempt failed
                        failed += 1
                        print(f"  [error] cluster {cluster_id}: {str(e)[:100]}")
                    else:
                        continue
            
            if not success:
                failed += 1
        
        # Rate limiting - wait between requests to avoid throttling
        time.sleep(RATE_LIMIT_DELAY)

    conn.close()
    print(f"Summarize done: {done}/{total} clusters. Failed: {failed}. (Using {LLM_PROVIDER.upper()})")
    return done


if __name__ == "__main__":
    summarize_clusters()
