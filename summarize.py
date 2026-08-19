"""
Stage 3: Summarize + rank.
For each new cluster, sends all its source articles to an LLM in one call and asks
for: a synthesized 2-3 sentence summary, and an importance score.

Real traffic runs through agents/reporter_agent.py's beat Reporter Agents (Gemini,
via agents/base_agent.py - see that file's docstring for why Claude/Groq were dropped
from the actual call path). The claude_client/groq_client + LLM_PROVIDER=="claude"/
"groq" branches below are a legacy fallback that only executes if REPORTERS_AVAILABLE
is False (agents/reporter_agent.py fails to import) - which, in this project's
history, has never happened. Kept only so a broken Reporter Agents import degrades to
*something* rather than summarize_clusters() silently doing nothing.
"""
import json
import time
import anthropic
from groq import Groq
from datetime import datetime, timedelta, timezone
from config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL, GROQ_API_KEY, GROQ_MODEL, LLM_PROVIDER,
    LOOKBACK_HOURS, SUMMARIZE_BATCH_SIZE, MAX_AUTO_SUMMARIZE_ATTEMPTS,
    SUMMARIZE_RETRY_COOLDOWN_SECONDS,
)
from db import get_connection

try:
    from agents.reporter_agent import summarize_cluster_with_beat_reporter
    REPORTERS_AVAILABLE = True
except ImportError:
    REPORTERS_AVAILABLE = False

# Initialize clients based on provider - only meaningful for the legacy fallback loop
# at the bottom of summarize_clusters() (see module docstring: REPORTERS_AVAILABLE is
# True in every environment this has actually run in, so that loop never executes).
# This used to raise ValueError and crash the whole process at IMPORT TIME - and since
# publish.py does `from summarize import ...` at its own module level, that took down
# the entire 15-min pipeline - for any LLM_PROVIDER value other than exactly "claude"
# or "groq". That included "gemini", the value that actually matches how the rest of
# the codebase runs (agents/base_agent.py is Gemini-only): confirmed via publish.log
# and `launchctl print` (exit code 1, crash-looping every 900s) on 2026-08-13 after
# .env's LLM_PROVIDER was set to "gemini" - killing every scheduled run over a code
# path that was never actually going to execute anyway. Not initializing a client for
# an unrecognized provider is fine; crashing the whole process on import over it isn't.
claude_client = None
groq_client = None
if LLM_PROVIDER == "claude":
    claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
elif LLM_PROVIDER == "groq":
    groq_client = Groq(api_key=GROQ_API_KEY)

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


def _infer_failure_reason(articles_present: bool) -> str:
    """Best-effort human-readable reason when a cluster fails without raising (call_llm
    returned None/empty, or the response wasn't valid JSON - see Agent.call_llm and
    ReporterAgent.summarize_cluster). Checks the shared circuit breaker so a UI reading
    clusters.summarize_error doesn't need to cross-reference agent_logs to tell "every
    provider is rate-limited right now" apart from "the model keeps returning garbage
    for this specific cluster"."""
    if not articles_present:
        return "no source articles (likely cleaned up by cleanup_old_articles before this ran)"
    try:
        from agents.base_agent import ALL_PROVIDERS
        from utils.error_handling import breaker
        if all(breaker.is_open(p) for p in ALL_PROVIDERS):
            return "all LLM providers (Claude/Groq/Gemini) are rate-limited or cooling down"
    except Exception:
        pass
    return "LLM returned no usable JSON (see agent_logs for the provider-level error)"


def _summarize_one_cluster(cluster_id):
    """Fetch a cluster's articles and summarize via the beat-specific Reporter Agent (Task 2.4).
    Returns (cluster_id, parsed_or_None, error_reason_or_None)."""
    conn = get_connection()
    articles = conn.execute(
        "SELECT id, source, title, url, summary_raw, published_at FROM articles WHERE cluster_id = ?",
        (cluster_id,),
    ).fetchall()
    conn.close()
    if not articles:
        return cluster_id, None, _infer_failure_reason(articles_present=False)
    try:
        parsed = summarize_cluster_with_beat_reporter([dict(a) for a in articles])
    except Exception as e:
        return cluster_id, None, str(e)[:300]
    if parsed is None:
        return cluster_id, None, _infer_failure_reason(articles_present=True)
    return cluster_id, parsed, None


def _apply_summarize_result(conn, cluster_id, parsed, error):
    """Persist one cluster's summarize outcome, including the attempt-tracking columns
    that back MAX_AUTO_SUMMARIZE_ATTEMPTS and the admin UI's Re-process button (see
    db.py's summarize_attempts/last_summarize_attempt_at/summarize_error migration)."""
    now = datetime.now(timezone.utc).isoformat()
    if parsed:
        conn.execute(
            """UPDATE clusters SET headline = ?, category = ?, summary = ?, importance_score = ?,
               content_type = ?, last_summarize_attempt_at = ?, summarize_error = NULL WHERE id = ?""",
            (parsed["headline"], parsed["category"], parsed["summary"], parsed["importance_score"],
             parsed.get("content_type", "news"), now, cluster_id),
        )
    else:
        conn.execute(
            """UPDATE clusters SET summarize_attempts = COALESCE(summarize_attempts, 0) + 1,
               last_summarize_attempt_at = ?, summarize_error = ? WHERE id = ?""",
            (now, (error or "unknown error")[:300], cluster_id),
        )
    conn.commit()


def _summarize_with_reporters(conn, clusters):
    """
    One cluster at a time across the beat Reporter Agents. Used to run 5 clusters
    concurrently via ThreadPoolExecutor - faster, but firing 5 LLM requests at once
    made it easy to burst past a provider's per-minute rate limit, tripping the
    circuit breaker (agents/base_agent.py) and falling through to backup providers
    (or, if a batch is big enough, exhausting all three) more often than a paced
    sequence of calls would. This runs unattended every 15 min via publish.py, so
    trading some wall-clock time for staying under rate limits in the first place
    is a clear win - a slower run beats one that trips every provider's breaker.
    """
    done = failed = 0
    total = len(clusters)

    for i, c in enumerate(clusters, 1):
        cluster_id = c["id"]
        _, parsed, error = _summarize_one_cluster(cluster_id)
        if error:
            print(f"  [error] cluster {cluster_id}: {error[:100]}")

        _apply_summarize_result(conn, cluster_id, parsed, error)
        if parsed:
            done += 1
        else:
            failed += 1

        if i % 10 == 0:
            print(f"  [{i}/{total}] {done} done, {failed} failed")

        time.sleep(RATE_LIMIT_DELAY)

    return done, failed


def summarize_clusters():
    conn = get_connection()

    # Query only clusters that:
    # 1. Have not been summarized yet (summary IS NULL)
    # 2. Have NOT been sent in an email digest yet (sent_at IS NULL) - Task 1.4
    #
    # NOTE: this used to also require created_at > last email digest's sent_at.
    # That silently orphaned any cluster that failed to summarize (e.g. during an
    # LLM outage) before the *next* email went out - once sent_at moved past its
    # created_at, it could never be picked up again, on the site or the email side.
    # publish.py runs every 15 min independent of the twice-daily email (see its
    # module docstring), so gating its batch on the email schedule was a bug, not
    # a feature. sent_at IS NULL is sufficient to avoid re-summarizing sent stuff.
    #
    # 3. Have NOT already burned through MAX_AUTO_SUMMARIZE_ATTEMPTS (cost control -
    #    see the constant's comment in config.py). Once a cluster hits the cap it
    #    stops being picked up automatically; it still shows up in the admin UI's
    #    failed-clusters list (api/main.py::list_failed_clusters) for a human to
    #    manually Re-process, which calls reprocess_cluster() below directly and
    #    ignores this cap - a deliberate one-off click, not an unattended retry loop.
    clusters = conn.execute("""
        SELECT id FROM clusters
        WHERE summary IS NULL
          AND sent_at IS NULL
          AND COALESCE(summarize_attempts, 0) < ?
        ORDER BY created_at ASC
        LIMIT ?
    """, (MAX_AUTO_SUMMARIZE_ATTEMPTS, SUMMARIZE_BATCH_SIZE)).fetchall()

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
        return 0, 0

    total = len(clusters)
    done = 0
    failed = 0

    print(f"Summarize: processing {total}/{total_unsummarized - sent_unsummarized} pending clusters...")

    if REPORTERS_AVAILABLE:
        done, failed = _summarize_with_reporters(conn, clusters)
        conn.close()
        print(f"Summarize done: {done}/{total} clusters. Failed: {failed}. (Using beat Reporter Agents)")
        return done, failed

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

        else:
            # LLM_PROVIDER is something other than "claude"/"groq" (e.g. "gemini") -
            # this legacy loop only ever implemented those two. Reaching this branch at
            # all means REPORTERS_AVAILABLE was False (the real Gemini-based path is
            # also unavailable) - so failing loudly here, instead of silently matching
            # neither branch and leaving the cluster stuck with no summary and no
            # failure recorded, is the honest outcome.
            failed += 1
            print(f"  [error] cluster {cluster_id}: legacy summarize path doesn't support "
                  f"LLM_PROVIDER={LLM_PROVIDER!r} (only 'claude'/'groq' implemented here), "
                  f"and Reporter Agents are unavailable - can't summarize right now")

        # Rate limiting - wait between requests to avoid throttling
        time.sleep(RATE_LIMIT_DELAY)

    conn.close()
    print(f"Summarize done: {done}/{total} clusters. Failed: {failed}. (Using {LLM_PROVIDER.upper()})")
    return done, failed


def reprocess_cluster(cluster_id: int, force: bool = False) -> dict:
    """Manually re-run summarization for one cluster - the backend for the admin UI's
    per-row "Re-process" button (api/main.py::reprocess_cluster_endpoint). This is the
    ONE path that's allowed to retry a cluster past MAX_AUTO_SUMMARIZE_ATTEMPTS - it's a
    single, explicit, human-initiated click, not an unattended loop, so the cost-control
    cap that governs summarize_clusters()'s automatic batch doesn't apply here.

    Still guards against the ways a manual retry could waste a call for nothing:
      - already summarized (e.g. a concurrent pipeline run beat the click to it) ->
        returns success without touching any LLM provider.
      - already sent in an email digest -> refused; summarize_clusters() never
        re-touches sent clusters and this shouldn't either.
      - no source articles left (cleanup_old_articles ran) -> refused before any LLM
        call, since it would just fail the same way every time.
      - clicked again inside SUMMARIZE_RETRY_COOLDOWN_SECONDS of the last attempt
        (double-click, two tabs, a retried network request) -> refused unless
        force=True, so it can't fire two LLM calls for the same cluster back to back.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT id, summary, sent_at, last_summarize_attempt_at, summarize_attempts FROM clusters WHERE id = ?",
        (cluster_id,),
    ).fetchone()
    if row is None:
        conn.close()
        return {"ok": False, "error": "cluster not found"}

    if row["summary"] is not None:
        conn.close()
        return {"ok": True, "already_summarized": True}

    if row["sent_at"] is not None:
        conn.close()
        return {"ok": False, "error": "cluster was already sent in an email digest, won't reprocess"}

    if not force and row["last_summarize_attempt_at"]:
        try:
            last = datetime.fromisoformat(row["last_summarize_attempt_at"])
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        except ValueError:
            elapsed = SUMMARIZE_RETRY_COOLDOWN_SECONDS  # unparseable timestamp -> don't block on it
        if elapsed < SUMMARIZE_RETRY_COOLDOWN_SECONDS:
            conn.close()
            wait = int(SUMMARIZE_RETRY_COOLDOWN_SECONDS - elapsed)
            return {"ok": False, "error": f"retried too recently, wait {wait}s", "retry_after_seconds": wait}

    if not REPORTERS_AVAILABLE:
        conn.close()
        return {"ok": False, "error": "reporter agents unavailable (agents/reporter_agent.py failed to import)"}

    conn.close()  # _summarize_one_cluster opens its own connection; keep the LLM call outside any open one

    _, parsed, error = _summarize_one_cluster(cluster_id)

    conn = get_connection()
    _apply_summarize_result(conn, cluster_id, parsed, error)
    updated = conn.execute(
        "SELECT headline, category, summary, importance_score, summarize_attempts, summarize_error FROM clusters WHERE id = ?",
        (cluster_id,),
    ).fetchone()
    conn.close()

    if parsed:
        return {"ok": True, "cluster": dict(updated)}
    return {"ok": False, "error": error or "unknown error", "attempts": updated["summarize_attempts"]}


if __name__ == "__main__":
    summarize_clusters()
