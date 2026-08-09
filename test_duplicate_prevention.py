#!/usr/bin/env python
"""
Integration Test: Duplicate Prevention Across Pipeline Runs
Tests Task 1.3 Acceptance Criteria: Running pipeline twice must show different stories

This test:
1. Sets up a test database with sample clusters
2. Runs the digest generation pipeline (first run)
3. Marks clusters as sent
4. Runs the digest generation pipeline again (second run)
5. Verifies that second run shows DIFFERENT stories (no duplicates)
"""
import sqlite3
import tempfile
import os
from datetime import datetime, timezone
from agents.state_manager import StateManager


def setup_test_database():
    """Create test database with sample clusters"""
    test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    test_db_path = test_db.name
    test_db.close()
    
    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row
    
    # Create schema
    from db import SCHEMA
    conn.executescript(SCHEMA)
    
    # Insert test clusters with articles
    now = datetime.now(timezone.utc).isoformat()
    
    test_clusters = [
        (1, now, "AI Breakthrough in Language Models", "Research & Models", 
         "New research shows significant improvements in language understanding.", 9.5, 0, None, None),
        (2, now, "OpenAI Announces New Product", "Company News",
         "OpenAI launches new API capabilities for developers.", 8.0, 0, None, None),
        (3, now, "Google's Latest AI Research", "Research & Models",
         "Google AI publishes groundbreaking paper on transformers.", 8.5, 0, None, None),
        (4, now, "Microsoft Invests in AI", "Funding & Business",
         "Microsoft announces $1B investment in AI infrastructure.", 7.5, 0, None, None),
        (5, now, "New AI Framework Released", "Tools & Engineering",
         "Open source community releases new deep learning framework.", 7.0, 0, None, None),
        (6, now, "AI Ethics Discussion", "Policy & Regulation",
         "Global summit addresses AI safety and ethics.", 6.5, 0, None, None),
    ]
    
    conn.executemany("""
        INSERT INTO clusters 
        (id, created_at, headline, category, summary, importance_score, 
         included_in_digest, sent_at, digest_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, test_clusters)
    
    # Insert sample articles for each cluster
    test_articles = [
        (1, "TechCrunch", "AI Breakthrough Announced", "https://example.com/1", now, now, 1),
        (2, "The Verge", "OpenAI Product Launch", "https://example.com/2", now, now, 2),
        (3, "ArXiv", "Google AI Research Paper", "https://example.com/3", now, now, 3),
        (4, "Bloomberg", "Microsoft AI Investment", "https://example.com/4", now, now, 4),
        (5, "GitHub", "New Framework Released", "https://example.com/5", now, now, 5),
        (6, "BBC", "AI Ethics Summit", "https://example.com/6", now, now, 6),
    ]
    
    conn.executemany("""
        INSERT INTO articles 
        (id, source, title, url, published_at, fetched_at, cluster_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, test_articles)
    
    conn.commit()
    conn.close()
    
    return test_db_path


def simulate_digest_generation(db_path, run_number):
    """Simulate digest generation pipeline"""
    print(f"\n{'='*70}")
    print(f"🤖 SIMULATING PIPELINE RUN #{run_number}")
    print('='*70)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Step 1: Get unsent clusters (this is what the pipeline does)
    print("\n[1] Fetching unsent clusters from database...")
    unsent_clusters = conn.execute("""
        SELECT * FROM clusters 
        WHERE sent_at IS NULL 
        ORDER BY importance_score DESC
        LIMIT 3
    """).fetchall()
    
    cluster_ids = [c['id'] for c in unsent_clusters]
    
    if not cluster_ids:
        print("   ⚠️  No unsent clusters available")
        conn.close()
        return []
    
    print(f"   ✓ Found {len(cluster_ids)} unsent clusters: {cluster_ids}")
    
    # Step 2: Get articles for each cluster
    print("\n[2] Fetching articles for clusters...")
    selected_stories = []
    for cluster in unsent_clusters:
        articles = conn.execute("""
            SELECT * FROM articles WHERE cluster_id = ?
        """, (cluster['id'],)).fetchall()
        
        story = {
            'id': cluster['id'],
            'headline': cluster['headline'],
            'category': cluster['category'],
            'summary': cluster['summary'],
            'importance_score': cluster['importance_score'],
            'articles': [dict(a) for a in articles]
        }
        selected_stories.append(story)
        print(f"   ✓ Cluster {cluster['id']}: {cluster['headline']}")
    
    conn.close()
    
    print(f"\n[3] Digest would include {len(selected_stories)} stories")
    
    return cluster_ids, selected_stories


def mark_stories_as_sent(db_path, cluster_ids, digest_id):
    """Mark clusters as sent using StateManager"""
    if not cluster_ids:
        return
    
    print(f"\n[4] Marking {len(cluster_ids)} clusters as sent (digest: {digest_id})...")
    
    # Temporarily override config.DB_PATH for StateManager
    import config
    original_db_path = config.DB_PATH
    config.DB_PATH = db_path
    
    manager = StateManager()
    manager.mark_as_sent(cluster_ids, digest_id)
    
    # Restore original path
    config.DB_PATH = original_db_path
    
    print(f"   ✓ Successfully marked clusters as sent")


def verify_no_duplicates(run1_ids, run2_ids):
    """Verify that run 2 has no overlap with run 1"""
    print(f"\n{'='*70}")
    print("🔍 VERIFYING DUPLICATE PREVENTION")
    print('='*70)
    
    print(f"\nRun 1 cluster IDs: {run1_ids}")
    print(f"Run 2 cluster IDs: {run2_ids}")
    
    overlap = set(run1_ids) & set(run2_ids)
    
    if overlap:
        print(f"\n❌ FAILURE: Found duplicate clusters: {overlap}")
        return False
    else:
        print(f"\n✅ SUCCESS: No duplicate clusters between runs")
        print(f"   • Run 1 sent {len(run1_ids)} stories")
        print(f"   • Run 2 sent {len(run2_ids)} stories")
        print(f"   • Zero overlap (as expected)")
        return True


def main():
    """Run the integration test"""
    print("="*70)
    print("🧪 INTEGRATION TEST: Duplicate Prevention Across Pipeline Runs")
    print("="*70)
    print("\nThis test validates Task 1.3 acceptance criteria:")
    print("'Running pipeline twice must show different stories'")
    
    # Setup
    print("\n[SETUP] Creating test database with 6 sample clusters...")
    db_path = setup_test_database()
    print(f"   ✓ Test database created: {db_path}")
    
    try:
        # First run
        run1_ids, run1_stories = simulate_digest_generation(db_path, 1)
        
        if run1_ids:
            mark_stories_as_sent(db_path, run1_ids, "2026-08-08-run1")
        
        # Second run
        run2_ids, run2_stories = simulate_digest_generation(db_path, 2)
        
        if run2_ids:
            mark_stories_as_sent(db_path, run2_ids, "2026-08-08-run2")
        
        # Verify
        success = verify_no_duplicates(run1_ids, run2_ids)
        
        # Additional verification: Check database state
        print("\n[DATABASE STATE CHECK]")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        sent_count = conn.execute("SELECT COUNT(*) as count FROM clusters WHERE sent_at IS NOT NULL").fetchone()['count']
        unsent_count = conn.execute("SELECT COUNT(*) as count FROM clusters WHERE sent_at IS NULL").fetchone()['count']
        
        print(f"   • Sent clusters: {sent_count}")
        print(f"   • Unsent clusters: {unsent_count}")
        
        conn.close()
        
        # Final verdict
        print("\n" + "="*70)
        if success and sent_count == len(run1_ids) + len(run2_ids):
            print("✅ INTEGRATION TEST PASSED")
            print("="*70)
            print("\n✓ StateManager successfully prevents duplicate content")
            print("✓ Running pipeline multiple times shows different stories")
            print("✓ Task 1.3 acceptance criteria satisfied")
            return 0
        else:
            print("❌ INTEGRATION TEST FAILED")
            print("="*70)
            return 1
        
    finally:
        # Cleanup
        print(f"\n[CLEANUP] Removing test database...")
        os.unlink(db_path)
        print("   ✓ Cleanup complete")


if __name__ == "__main__":
    exit(main())
