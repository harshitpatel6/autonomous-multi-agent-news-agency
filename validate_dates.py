"""
Comprehensive date validation script.
Run this after the pipeline to ensure NO old articles slip through.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
from config import DB_PATH, LOOKBACK_HOURS, ABSOLUTE_CUTOFF_DATE

def validate_all_dates():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    print("\n" + "="*70)
    print("DATE VALIDATION REPORT")
    print("="*70)
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    cutoff_str = cutoff.isoformat()
    absolute_cutoff = datetime.fromisoformat(ABSOLUTE_CUTOFF_DATE)
    
    print(f"\nLOOKBACK_HOURS: {LOOKBACK_HOURS} (cutoff: {cutoff_str[:19]})")
    print(f"ABSOLUTE_CUTOFF_DATE: {ABSOLUTE_CUTOFF_DATE[:19]}")
    
    # Check all articles
    all_articles = conn.execute("SELECT id, source, title, published_at, fetched_at, cluster_id FROM articles").fetchall()
    
    print(f"\n📊 TOTAL ARTICLES IN DB: {len(all_articles)}")
    
    # Categorize articles
    very_old = []  # Before ABSOLUTE_CUTOFF_DATE
    old = []  # Before LOOKBACK_HOURS cutoff
    recent = []  # Within LOOKBACK_HOURS
    no_date = []  # No published_at
    
    for article in all_articles:
        pub_date = article["published_at"]
        
        if not pub_date:
            no_date.append(article)
        elif pub_date < ABSOLUTE_CUTOFF_DATE:
            very_old.append(article)
        elif pub_date < cutoff_str:
            old.append(article)
        else:
            recent.append(article)
    
    print(f"\n📅 ARTICLE AGE BREAKDOWN:")
    print(f"  ✅ Recent (within {LOOKBACK_HOURS}h): {len(recent)}")
    print(f"  ⚠️  Old (before {LOOKBACK_HOURS}h cutoff): {len(old)}")
    print(f"  🚨 VERY OLD (before {ABSOLUTE_CUTOFF_DATE[:10]}): {len(very_old)}")
    print(f"  ❓ No date: {len(no_date)}")
    
    # Show problematic articles
    if very_old:
        print(f"\n🚨 CRITICAL: Found {len(very_old)} articles older than {ABSOLUTE_CUTOFF_DATE[:10]}!")
        print("   These should have been filtered during ingestion.")
        print("\n   Sample very old articles:")
        for article in very_old[:5]:
            clustered = "CLUSTERED" if article["cluster_id"] else "unclustered"
            print(f"     {article['published_at'][:10]} | [{article['source']}] {article['title'][:60]}... ({clustered})")
        
        if any(a["cluster_id"] for a in very_old):
            print("\n   ⚠️  WARNING: Some very old articles are CLUSTERED and may appear in digest!")
    
    if old:
        print(f"\n⚠️  Found {len(old)} articles older than {LOOKBACK_HOURS}h lookback window")
        print("   Sample old articles:")
        for article in old[:3]:
            clustered = "CLUSTERED" if article["cluster_id"] else "unclustered"
            print(f"     {article['published_at'][:10]} | [{article['source']}] {article['title'][:60]}... ({clustered})")
    
    # Check clusters
    clusters = conn.execute("""
        SELECT c.id, c.headline, c.created_at, c.included_in_digest
        FROM clusters c
        WHERE c.summary IS NOT NULL
    """).fetchall()
    
    print(f"\n📦 CLUSTERS:")
    print(f"  Total clusters: {len(clusters)}")
    
    clusters_with_old_articles = []
    for cluster in clusters:
        articles_in_cluster = conn.execute("""
            SELECT published_at FROM articles WHERE cluster_id = ?
        """, (cluster["id"],)).fetchall()
        
        for a in articles_in_cluster:
            if a["published_at"] and a["published_at"] < ABSOLUTE_CUTOFF_DATE:
                clusters_with_old_articles.append({
                    "cluster": cluster,
                    "old_article_date": a["published_at"]
                })
                break
    
    if clusters_with_old_articles:
        print(f"\n🚨 CRITICAL: {len(clusters_with_old_articles)} clusters contain very old articles!")
        for item in clusters_with_old_articles[:5]:
            print(f"     Cluster: {item['cluster']['headline']}")
            print(f"     Contains article from: {item['old_article_date'][:10]}")
    else:
        print(f"  ✅ All clusters contain only recent articles")
    
    conn.close()
    
    # Final verdict
    print("\n" + "="*70)
    if very_old or clusters_with_old_articles:
        print("❌ VALIDATION FAILED")
        print("\nACTION REQUIRED:")
        print("1. Delete database: rm digest.db")
        print("2. Run pipeline again: python main.py")
        print("="*70)
        return False
    elif old:
        print("⚠️  VALIDATION WARNING: Some articles older than lookback window")
        print("   (This is OK if they're unclustered - they'll be cleaned up next run)")
        print("="*70)
        return True
    else:
        print("✅ VALIDATION PASSED - All articles are recent!")
        print("="*70)
        return True

if __name__ == "__main__":
    validate_all_dates()
