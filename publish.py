"""
Site publish job: runs frequently (every 15 min via launchd) to get new stories live
on the website fast, independent of the twice-daily email digest in main.py.

Pipeline: ingest -> cleanup -> cluster -> summarize (Reporter) -> Fact-Checker + QA
validate -> Writer full article -> mark clusters.published_at.

Does NOT touch sent_at/digest_id/included_in_digest — those stay purely email-side
state, owned by digest.py / main.py. A story can go live here and still show up in
the next email recap; that's normal digest behavior, not a conflict.
"""
import json
import os
from datetime import datetime, timezone

from config import (
    DB_PATH, MIN_IMPORTANCE_SCORE, MAX_PUBLISH_ATTEMPTS, PUBLISH_CANDIDATE_BATCH_SIZE,
    MAX_FULL_CONTENT_RETRY_ATTEMPTS,
)
from db import init_db, get_connection
from ingest import fetch_feeds
from dedup import cluster_articles
from summarize import summarize_clusters, cleanup_old_articles
from utils.error_classify import classify_error

from agents.message_router import router
from agents import qa_agent as _qa_module          # noqa: F401  (registers with router)
from agents import fact_checker_agent as _fc_module  # noqa: F401
from agents.qa_agent import qa_agent
from agents.writer_agent import ensure_full_article, backfill_missing_images
from agents.seo_agent import seo_agent

# Cap on how many already-published-but-missing-full_content articles to retry per
# run. Writer calls can fail transiently (LLM rate limits, provider errors) - a
# published cluster shouldn't be stuck without a full article forever, but retrying
# an unbounded backlog every 15 min could burn through LLM quota fast.
FULL_CONTENT_RETRY_BATCH = 10


def get_publish_candidates(limit: int = PUBLISH_CANDIDATE_BATCH_SIZE):
    """Summarized clusters that haven't been published to the site yet.

    Excludes clusters already given up on (validation_status='rejected' - see
    _record_publish_attempt) and caps the batch, same as summarize_clusters()/
    seo_agent's sweep - a run should never try to drag an unbounded backlog through
    the full fact-check -> Writer -> defamation-check LLM pipeline in one go."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, headline, category, summary, importance_score, created_at, content_type
        FROM clusters
        WHERE summary IS NOT NULL
              AND published_at IS NULL
              AND importance_score >= ?
              AND (validation_status IS NULL OR validation_status != 'rejected')
        ORDER BY importance_score DESC
        LIMIT ?
    """, (MIN_IMPORTANCE_SCORE, limit)).fetchall()

    result = []
    for cluster in rows:
        # id + summary_raw are required, not decorative: check_content_grounding()
        # (agents/fact_checker_agent.py) uses article "id" to look up the cached
        # full-article text (utils.fulltext.get_full_text) - the same material the
        # Writer actually used to write the piece - and falls back to summary_raw if
        # there's no full-text cache. Without them here it silently checked the
        # generated article against an empty body ("" for every article) and
        # confidently declared every real, sourced fact "fabricated" because from its
        # point of view no source material existed at all - the actual mechanism
        # behind the near-100% grounding-check failure rate seen in production
        # (2026-08-13): the fix to check_content_grounding's own truncation was a
        # necessary but insufficient fix on its own while this query fed it nothing
        # to work with in the first place.
        articles = conn.execute(
            "SELECT id, source, title, url, summary_raw, published_at, fetched_at FROM articles WHERE cluster_id = ?",
            (cluster["id"],),
        ).fetchall()
        cluster_dict = dict(cluster)
        cluster_dict["articles"] = [dict(a) for a in articles]
        result.append(cluster_dict)

    conn.close()
    return result


def _record_publish_attempt(cluster_id: int, reason: str):
    """Bump this cluster's failure count on a failed publish attempt; give up
    permanently (validation_status='rejected') once it's failed MAX_PUBLISH_ATTEMPTS
    times, so a story that will never pass doesn't get re-run through Writer's
    2200-token LLM call every 15-min cycle forever. Rejected clusters stay in the DB
    (nothing is deleted) so a human can inspect/reset them - see publish_attempts."""
    conn = get_connection()
    row = conn.execute("SELECT publish_attempts FROM clusters WHERE id = ?", (cluster_id,)).fetchone()
    attempts = (row["publish_attempts"] or 0) + 1 if row else 1
    now = datetime.now(timezone.utc).isoformat()
    if attempts >= MAX_PUBLISH_ATTEMPTS:
        conn.execute(
            "UPDATE clusters SET publish_attempts = ?, last_publish_attempt_at = ?, validation_status = 'rejected' WHERE id = ?",
            (attempts, now, cluster_id),
        )
        print(f"  [give-up] cluster {cluster_id}: failed {attempts}x ({reason}) — marked rejected, won't retry again")
    else:
        conn.execute(
            "UPDATE clusters SET publish_attempts = ?, last_publish_attempt_at = ? WHERE id = ?",
            (attempts, now, cluster_id),
        )
    conn.commit()
    conn.close()


def publish_ready_clusters(clusters):
    """Fact-check + QA each candidate; publish (write full article, set published_at) if it passes."""
    published_ids = []

    for cluster in clusters:
        fc_response = router.send(
            "publish_job", "fact_checker", "validate_cluster",
            {"cluster": cluster, "articles": cluster["articles"]},
        )
        recommendation = fc_response.get("recommendation") if fc_response else None
        if recommendation == "reject":
            # A genuine data-quality problem (missing headline/summary, unparseable/
            # implausible dates, malformed URLs) - no LLM call is going to fix that, so
            # hold without spending one.
            reason = f"fact-check rejected: {'; '.join((fc_response or {}).get('flags', []))}"
            _record_publish_attempt(cluster["id"], reason)
            continue
        if recommendation != "publish" and recommendation != "review":
            # fc_response missing/malformed (router error, fact-checker exception, etc.)
            _record_publish_attempt(cluster["id"], "fact-check unavailable")
            continue
        # "review" (in practice, almost always validate_cluster's single-uncorroborated-
        # source heuristic - see agents/fact_checker_agent.py) used to be held here right
        # alongside "reject", on the theory that "a follow-up ingest cycle may add a
        # corroborating source to the same cluster." That never actually happens:
        # dedup.py::cluster_articles() only ever groups brand-new unclustered articles
        # into brand-new clusters - it never merges a later-arriving article into an
        # existing one - so a single-source cluster stays single-source forever. Verified
        # against the live DB (2026-08-13): 108 of 111 clusters stuck unpublished, and 45
        # of 49 permanently marked 'rejected', were single-source - retried 5 identical
        # times against an input that never changes, then killed. That's most AI-news
        # coverage: an official vendor/project blog (Cloudflare, the PSF, JetBrains, ...)
        # announcing its own release is inherently single-source, with no third party
        # ever going to "corroborate" it.
        #
        # The actual risk a low source count was a rough proxy for - one uncorroborated
        # source making a claim about a THIRD PARTY, with no way to check it - is exactly
        # what check_content_grounding()'s defamation check below verifies directly,
        # against the real generated text, which is a far more precise signal than "how
        # many sources back the editorial brief." So "review" now proceeds through
        # Writer + grounding-check like "publish"; only a genuine "reject" short-circuits
        # before spending an LLM call.

        qa_result = qa_agent.validate_clusters_for_digest([cluster], min_count=0)
        if not qa_result["valid_clusters"]:
            _record_publish_attempt(cluster["id"], "QA rejected")
            continue

        if not ensure_full_article(cluster):
            # Writer Agent failed (LLM providers down/rate-limited/etc.) - leave
            # published_at unset so this stays a publish candidate and gets retried
            # on a later run (up to MAX_PUBLISH_ATTEMPTS), instead of going live with
            # no full_content (which renders as the same short summary repeated 3x
            # on the article page).
            _record_publish_attempt(cluster["id"], "Writer/LLM failed")
            continue

        conn = get_connection()
        row = conn.execute(
            "SELECT full_content, key_takeaways FROM clusters WHERE id = ?", (cluster["id"],)
        ).fetchone()
        conn.close()
        generated_text = (row["full_content"] or "") if row else ""
        if row and row["key_takeaways"]:
            try:
                generated_text += "\n" + "\n".join(json.loads(row["key_takeaways"]))
            except (TypeError, ValueError):
                pass

        compliance = router.send(
            "publish_job", "fact_checker", "check_content_grounding",
            {"headline": cluster.get("headline"), "generated_text": generated_text, "articles": cluster["articles"]},
        )
        if not compliance or compliance.get("verdict") != "PASS":
            # Fail closed: don't publish a story the grounding check couldn't clear -
            # covers both defamation risk and fabricated/distorted numbers or facts the
            # Writer introduced while expanding the sources. Left unpublished (not
            # deleted) so a human can review flagged claims via agent_logs and, if it's
            # a false positive, republish it manually.
            print(f"  [blocked] cluster {cluster['id']} failed grounding check: "
                  f"{(compliance or {}).get('flagged')}")
            # ensure_full_article() caches full_content/key_takeaways permanently once
            # generated, so without this a FAIL here was terminal: every later retry
            # (up to MAX_PUBLISH_ATTEMPTS) re-ran check_content_grounding against the
            # exact same cached text and was guaranteed to fail identically, burning the
            # whole retry budget for zero chance of ever passing. Clearing the cache
            # makes the next attempt regenerate a fresh article via the Writer instead -
            # a real second chance rather than a re-run of a foregone conclusion.
            conn = get_connection()
            conn.execute(
                "UPDATE clusters SET full_content = NULL, key_takeaways = NULL WHERE id = ?",
                (cluster["id"],),
            )
            conn.commit()
            conn.close()
            _record_publish_attempt(cluster["id"], "grounding check failed")
            continue

        conn = get_connection()
        conn.execute(
            "UPDATE clusters SET published_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), cluster["id"]),
        )
        conn.commit()
        conn.close()
        published_ids.append(cluster["id"])

    return published_ids


def retry_missing_full_content(limit: int = FULL_CONTENT_RETRY_BATCH):
    """
    Already-published clusters missing full_content and/or key_takeaways - either the
    Writer call failed the first time (e.g. LLM rate limit), or the cluster was published
    before key_takeaways existed. Retried in small batches on later runs so they self-heal
    instead of being permanently stuck showing only the short summary.

    Excludes clusters that have already failed MAX_FULL_CONTENT_RETRY_ATTEMPTS times
    (originality_attempts, bumped by ensure_full_article() on every failure) - same
    retry-storm guard as MAX_PUBLISH_ATTEMPTS above. A cluster whose only source is too
    thin/quotable to ever clear utils/similarity.py's gate will fail identically forever;
    past the cap it's left showing its short summary rather than burning a Gemini call
    every 15 minutes indefinitely for zero chance of a different outcome.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, headline, category, summary, importance_score, content_type FROM clusters
        WHERE published_at IS NOT NULL
              AND (full_content IS NULL OR full_content = '' OR key_takeaways IS NULL)
              AND COALESCE(originality_attempts, 0) < ?
        ORDER BY published_at ASC LIMIT ?
    """, (MAX_FULL_CONTENT_RETRY_ATTEMPTS, limit)).fetchall()
    conn.close()

    retried = 0
    for row in rows:
        ensure_full_article(dict(row))
        retried += 1
    return retried


def _provider_from_action(action: str):
    """'call_llm[groq]' -> 'groq'; 'call_llm' (the final all-exhausted log line) -> None."""
    if action.startswith("call_llm[") and action.endswith("]"):
        return action[len("call_llm["):-1]
    return None


def summarize_run_errors(conn, since: str, limit: int = 5):
    """Top error reasons logged by any agent during THIS run, most frequent first, e.g.
    '3x groq: daily quota exceeded'. Provider comes from agent_logs.action
    ('call_llm[groq]'), not from guessing at message wording, so this scales to
    however many providers base_agent.py has configured without hardcoded names.

    Scoped by pid, not just the timestamp window: agent_logs is a shared table, and any
    other script that touches an Agent while this run's window is open - a background
    rewrite_at_risk_articles.py pass, insights.py, a manually-triggered digest.py - writes
    to the exact same table. A timestamp-only filter used to fold that concurrent script's
    failures into THIS run's "Top errors" on the Processing History page, even on cycles
    with zero real candidates of its own (misdiagnosed 2026-08-15: a 44-min corpus-rewrite
    background job made routine 15-min publish cycles look like every candidate was
    failing originality/quality checks, when in fact those cycles had no candidates at all
    and were just reporting the other process's in-progress retry attempts)."""
    rows = conn.execute(
        "SELECT action, error_message FROM agent_logs WHERE timestamp >= ? AND success = 0 AND error_message IS NOT NULL AND pid = ?",
        (since, os.getpid()),
    ).fetchall()
    counts: dict = {}
    for r in rows:
        provider = _provider_from_action(r["action"])
        reason = classify_error(r["error_message"])
        label = f"{provider}: {reason}" if provider else reason
        counts[label] = counts.get(label, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{"reason": reason, "count": count} for reason, count in ranked]


def run():
    print("=" * 70)
    print("📡 SITE PUBLISH JOB - checking for new stories")
    print("=" * 70)

    init_db()
    started_at = datetime.now(timezone.utc).isoformat()

    print("\n[1/4] Ingesting feeds...")
    ingest_stats = fetch_feeds()

    print("\n[2/4] Cleaning up old articles...")
    cleanup_old_articles()

    print("\n[3/4] Clustering + summarizing new articles...")
    new_clusters = cluster_articles()
    summarized_ok, summarized_failed = summarize_clusters()

    print("\n[4/4] Validating + publishing new stories to the site...")
    candidates = get_publish_candidates()
    print(f"📦 {len(candidates)} candidate(s) awaiting publish decision")
    published_ids = publish_ready_clusters(candidates)

    print(f"\n✅ Published {len(published_ids)}/{len(candidates)} new stories to the site: {published_ids}")

    retried = retry_missing_full_content()
    if retried:
        print(f"♻️  Retried full-article generation for {retried} previously-published stories")

    backfilled = backfill_missing_images()
    if backfilled:
        print(f"🖼️  Backfilled lead images for {backfilled} previously-published stories")

    # SEO Agent: audits new articles first, then the most stale re-audits, every
    # run - fully autonomous, no manual trigger needed (see agents/seo_agent.py).
    seo_result = seo_agent.audit_site()
    if seo_result["checked"]:
        trend_str = f" ({seo_result['trend']:+.1f} vs last run)" if seo_result.get("trend") is not None else ""
        print(f"🔍 SEO Agent: audited {seo_result['checked']} article(s), avg score {seo_result['avg_score']}{trend_str}")
    if seo_result["site_issues"]:
        print(f"   ⚠️  {len(seo_result['site_issues'])} site-wide issue(s): {seo_result['site_issues'][:3]}")

    conn = get_connection()
    error_summary = summarize_run_errors(conn, started_at)
    conn.execute(
        """INSERT INTO pipeline_runs
           (started_at, finished_at, new_articles, old_articles_filtered, feed_errors,
            clusters_pending, clusters_summarized_ok, clusters_summarized_failed,
            publish_candidates, published_count, published_ids, error_summary)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            started_at,
            datetime.now(timezone.utc).isoformat(),
            ingest_stats["new"],
            ingest_stats["old"],
            ingest_stats["errors"],
            new_clusters,
            summarized_ok,
            summarized_failed,
            len(candidates),
            len(published_ids),
            json.dumps(published_ids),
            json.dumps(error_summary),
        ),
    )
    conn.commit()
    conn.close()

    if error_summary:
        print("\n⚠️  Top errors this run:")
        for e in error_summary:
            print(f"   {e['count']}x {e['reason']}")

    print("=" * 70)


if __name__ == "__main__":
    run()
