"""
Runs the full pipeline with Multi-Agent AI System
Autonomous agents handle all editorial decisions
"""
import argparse
import sys
from datetime import datetime, timezone

from db import init_db, get_connection
from ingest import fetch_feeds
from dedup import cluster_articles
from summarize import summarize_clusters, cleanup_old_articles
from digest import build_digest_html, mark_as_sent
from send_email import send_digest
from utils.api_validator import validate_api_keys_on_startup
from config import DIGEST_MIN_INTERVAL_HOURS


def _hours_since_last_digest() -> float | None:
    """None if no digest has ever been sent (always OK to run)."""
    conn = get_connection()
    row = conn.execute("SELECT MAX(sent_at) AS last_sent FROM digest_log").fetchone()
    conn.close()
    if not row or not row["last_sent"]:
        return None
    last_sent = datetime.fromisoformat(row["last_sent"].replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - last_sent).total_seconds() / 3600


def run(force: bool = False):
    print("=" * 70)
    print("🤖 AI NEWS AGENCY - Autonomous Multi-Agent Pipeline")
    print("=" * 70)

    # Validate API keys before proceeding
    try:
        validate_api_keys_on_startup()
    except RuntimeError as e:
        print(f"\n❌ STARTUP FAILED: {e}")
        return

    init_db()

    # Runs on a short recurring schedule now (see com.newletter.digest.plist) rather
    # than fixed clock times, so it self-catches-up whenever the machine is actually
    # on. This guard is what keeps that from sending duplicate digests every cycle.
    if not force:
        hours = _hours_since_last_digest()
        if hours is not None and hours < DIGEST_MIN_INTERVAL_HOURS:
            print(f"\n⏭  Last digest sent {hours:.1f}h ago (< {DIGEST_MIN_INTERVAL_HOURS}h) — skipping this cycle.")
            print("   Use `python3 main.py --force` to send immediately anyway.")
            return

    print("\n[1/5] Ingesting feeds...")
    fetch_feeds()

    print("\n[2/5] Cleaning up old articles...")
    cleanup_old_articles()

    print("\n[3/5] Clustering articles...")
    cluster_articles()

    print("\n[4/5] Summarizing clusters...")
    summarize_clusters()

    print("\n[5/5] Building digest (Multi-Agent Validation)...")
    html, cluster_ids = build_digest_html()

    if html is None:
        print("\n⚠️  No valid content for digest. Agents rejected all stories.")
        print("This could mean:")
        print("  • All articles were too old (filtered by QA Agent)")
        print("  • No articles met quality standards (Fact-Checker)")
        print("  • Editor found no stories worth publishing")
        return

    print("\n[6/5] Sending digest...")
    send_digest(html, cluster_ids=cluster_ids)
    mark_as_sent(cluster_ids)

    print("\n" + "=" * 70)
    print("✅ PIPELINE COMPLETE - Newsletter sent successfully")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI News Agency pipeline")
    parser.add_argument(
        "--force", action="store_true",
        help="Run and send immediately, bypassing the min-interval-since-last-digest guard.",
    )
    args = parser.parse_args()
    run(force=args.force)
