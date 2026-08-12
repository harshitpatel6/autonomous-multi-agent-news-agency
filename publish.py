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
from datetime import datetime, timezone

from config import DB_PATH, MIN_IMPORTANCE_SCORE
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


def get_publish_candidates():
    """Summarized clusters that haven't been published to the site yet."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, headline, category, summary, importance_score, created_at
        FROM clusters
        WHERE summary IS NOT NULL
              AND published_at IS NULL
              AND importance_score >= ?
        ORDER BY importance_score DESC
    """, (MIN_IMPORTANCE_SCORE,)).fetchall()

    result = []
    for cluster in rows:
        articles = conn.execute(
            "SELECT source, title, url, published_at, fetched_at FROM articles WHERE cluster_id = ?",
            (cluster["id"],),
        ).fetchall()
        cluster_dict = dict(cluster)
        cluster_dict["articles"] = [dict(a) for a in articles]
        result.append(cluster_dict)

    conn.close()
    return result


def publish_ready_clusters(clusters):
    """Fact-check + QA each candidate; publish (write full article, set published_at) if it passes."""
    published_ids = []

    for cluster in clusters:
        fc_response = router.send(
            "publish_job", "fact_checker", "validate_cluster",
            {"cluster": cluster, "articles": cluster["articles"]},
        )
        if not fc_response or fc_response.get("recommendation") not in ("publish", "review"):
            continue

        qa_result = qa_agent.validate_clusters_for_digest([cluster], min_count=0)
        if not qa_result["valid_clusters"]:
            continue

        if not ensure_full_article(cluster):
            # Writer Agent failed (LLM providers down/rate-limited/etc.) - leave
            # published_at unset so this stays a publish candidate and gets retried
            # on the next run, instead of going live with no full_content (which
            # renders as the same short summary repeated 3x on the article page).
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
            "publish_job", "fact_checker", "check_defamation_risk",
            {"headline": cluster.get("headline"), "generated_text": generated_text, "articles": cluster["articles"]},
        )
        if not compliance or compliance.get("verdict") != "PASS":
            # Fail closed: don't publish a story the compliance check couldn't clear.
            # Left unpublished (not deleted) so a human can review flagged claims via
            # agent_logs and, if it's a false positive, republish it manually.
            print(f"  [blocked] cluster {cluster['id']} failed defamation-risk check: "
                  f"{(compliance or {}).get('flagged')}")
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
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, headline, category, summary, importance_score FROM clusters
        WHERE published_at IS NOT NULL
              AND (full_content IS NULL OR full_content = '' OR key_takeaways IS NULL)
        ORDER BY published_at ASC LIMIT ?
    """, (limit,)).fetchall()
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
    """Top error reasons logged by any agent during this run, most frequent first, e.g.
    '3x groq: daily quota exceeded'. Provider comes from agent_logs.action
    ('call_llm[groq]'), not from guessing at message wording, so this scales to
    however many providers base_agent.py has configured without hardcoded names."""
    rows = conn.execute(
        "SELECT action, error_message FROM agent_logs WHERE timestamp >= ? AND success = 0 AND error_message IS NOT NULL",
        (since,),
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
