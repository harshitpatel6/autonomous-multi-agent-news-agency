"""
Runs the full pipeline with Multi-Agent AI System
Autonomous agents handle all editorial decisions
"""
from db import init_db
from ingest import fetch_feeds
from dedup import cluster_articles
from summarize import summarize_clusters, cleanup_old_articles
from digest import build_digest_html, mark_as_sent
from send_email import send_digest
from utils.api_validator import validate_api_keys_on_startup


def run():
    print("="*70)
    print("🤖 AI NEWS AGENCY - Autonomous Multi-Agent Pipeline")
    print("="*70)
    
    # Validate API keys before proceeding
    try:
        validation_results = validate_api_keys_on_startup()
    except RuntimeError as e:
        print(f"\n❌ STARTUP FAILED: {e}")
        return
    
    init_db()

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

    print("\n" + "="*70)
    print("✅ PIPELINE COMPLETE - Newsletter sent successfully")
    print("="*70)


if __name__ == "__main__":
    run()
