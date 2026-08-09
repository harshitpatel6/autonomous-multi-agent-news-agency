"""
Test script to verify date filtering is working correctly.
Run this after the full pipeline to check if old articles are being filtered.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
from config import DB_PATH, LOOKBACK_HOURS

def test_articles_in_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # Check all articles in DB
    all_articles = conn.execute("SELECT id, source, title, published_at, fetched_at FROM articles").fetchall()
    
    print(f"\n=== Database contains {len(all_articles)} articles ===\n")
    
    # Analyze published dates
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    cutoff_str = cutoff.isoformat()
    
    old_articles = []
    recent_articles = []
    no_date_articles = []
    
    for article in all_articles:
        pub_date = article["published_at"]
        
        if not pub_date:
            no_date_articles.append(article)
        elif pub_date < cutoff_str:
            old_articles.append(article)
        else:
            recent_articles.append(article)
    
    print(f"Recent articles (within {LOOKBACK_HOURS}h): {len(recent_articles)}")
    print(f"Old articles (older than {LOOKBACK_HOURS}h): {len(old_articles)}")
    print(f"Articles with no date: {len(no_date_articles)}")
    
    if old_articles:
        print(f"\n🚨 PROBLEM: Found {len(old_articles)} old articles that should have been filtered!")
        print("\nSample old articles:")
        for article in old_articles[:5]:
            print(f"  - {article['published_at'][:10]} | [{article['source']}] {article['title'][:80]}")
        print(f"\n⚠️  These old articles should NOT be in the database.")
        print("   Solution: Run 'rm digest.db' and then run the pipeline again.")
    else:
        print("\n✅ GOOD: No old articles found. Date filtering is working!")
    
    # Check clustered articles
    clustered = conn.execute("""
        SELECT COUNT(*) as count FROM articles WHERE cluster_id IS NOT NULL
    """).fetchone()["count"]
    
    unclustered = conn.execute("""
        SELECT COUNT(*) as count FROM articles WHERE cluster_id IS NULL
    """).fetchone()["count"]
    
    print(f"\nClustered articles: {clustered}")
    print(f"Unclustered articles: {unclustered}")
    
    # Check clusters
    clusters = conn.execute("SELECT COUNT(*) as count FROM clusters").fetchone()["count"]
    summarized = conn.execute("SELECT COUNT(*) as count FROM clusters WHERE summary IS NOT NULL").fetchone()["count"]
    
    print(f"\nTotal clusters: {clusters}")
    print(f"Summarized clusters: {summarized}")
    
    conn.close()
    
    return len(old_articles) == 0

if __name__ == "__main__":
    success = test_articles_in_db()
    if not success:
        print("\n" + "="*60)
        print("ACTION REQUIRED:")
        print("1. Delete the database: rm digest.db")
        print("2. Run the pipeline again: python3 main.py")
        print("="*60)
