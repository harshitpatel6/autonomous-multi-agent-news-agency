"""
Unit tests for StateManager - Sent Content Tracking
Tests for Task 1.3: State Manager - Sent Content Tracking
"""
import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta, timezone
from agents.state_manager import StateManager
from db import get_connection, init_db
from config import DB_PATH


@pytest.fixture
def setup_test_db(monkeypatch):
    """Setup a test database with sample clusters"""
    # Create temporary database for testing
    test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    test_db_path = test_db.name
    test_db.close()
    
    # Override DB_PATH at module level for all imports
    monkeypatch.setattr('config.DB_PATH', test_db_path)
    monkeypatch.setattr('db.DB_PATH', test_db_path)
    
    # Initialize database schema directly in test database
    conn = sqlite3.connect(test_db_path)
    from db import SCHEMA
    conn.executescript(SCHEMA)
    conn.commit()
    
    # Insert test clusters
    now = datetime.now(timezone.utc).isoformat()
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    old_date = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
    
    test_clusters = [
        (1, now, "Test Headline 1", "Company News", "Summary 1", 8.5, 0, None, None),
        (2, now, "Test Headline 2", "Research", "Summary 2", 7.0, 0, None, None),
        (3, now, "Test Headline 3", "Tools", "Summary 3", 9.0, 0, None, None),
        (4, yesterday, "Old Headline", "Policy", "Summary 4", 6.0, 1, yesterday, "2026-01-01-daily"),
        (5, old_date, "Very Old", "Other", "Summary 5", 5.0, 1, old_date, "2025-12-01-daily"),
    ]
    
    conn.executemany("""
        INSERT INTO clusters 
        (id, created_at, headline, category, summary, importance_score, 
         included_in_digest, sent_at, digest_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, test_clusters)
    
    conn.commit()
    conn.close()
    
    yield test_db_path
    
    # Cleanup
    os.unlink(test_db_path)


def test_state_manager_initialization():
    """Test that StateManager initializes correctly"""
    manager = StateManager()
    assert manager is not None


def test_mark_as_sent(setup_test_db):
    """Test marking clusters as sent"""
    manager = StateManager()
    
    # Mark clusters 1 and 2 as sent
    cluster_ids = [1, 2]
    digest_id = "2026-08-08-daily"
    
    result = manager.mark_as_sent(cluster_ids, digest_id)
    
    # Verify return count
    assert result == 2
    
    # Verify database updates
    conn = sqlite3.connect(setup_test_db)
    conn.row_factory = sqlite3.Row
    
    cluster1 = conn.execute("SELECT * FROM clusters WHERE id = 1").fetchone()
    cluster2 = conn.execute("SELECT * FROM clusters WHERE id = 2").fetchone()
    
    assert cluster1['sent_at'] is not None
    assert cluster1['digest_id'] == digest_id
    assert cluster1['included_in_digest'] == 1
    
    assert cluster2['sent_at'] is not None
    assert cluster2['digest_id'] == digest_id
    assert cluster2['included_in_digest'] == 1
    
    conn.close()


def test_mark_as_sent_empty_list(setup_test_db):
    """Test marking empty list returns 0"""
    manager = StateManager()
    result = manager.mark_as_sent([], "test-digest")
    assert result == 0


def test_filter_unsent_clusters(setup_test_db):
    """Test filtering out already-sent clusters"""
    manager = StateManager()
    
    # Get all clusters
    conn = sqlite3.connect(setup_test_db)
    conn.row_factory = sqlite3.Row
    
    all_clusters = conn.execute("SELECT * FROM clusters").fetchall()
    clusters_list = [dict(row) for row in all_clusters]
    
    conn.close()
    
    # Filter unsent
    unsent = manager.filter_unsent_clusters(clusters_list)
    
    # Should have 3 unsent clusters (IDs 1, 2, 3)
    assert len(unsent) == 3
    
    # Verify correct clusters are returned
    unsent_ids = [c['id'] for c in unsent]
    assert 1 in unsent_ids
    assert 2 in unsent_ids
    assert 3 in unsent_ids
    assert 4 not in unsent_ids  # Already sent
    assert 5 not in unsent_ids  # Already sent


def test_filter_unsent_clusters_empty_list(setup_test_db):
    """Test filtering empty list returns empty list"""
    manager = StateManager()
    result = manager.filter_unsent_clusters([])
    assert result == []


def test_get_unsent_cluster_ids(setup_test_db):
    """Test retrieving unsent cluster IDs"""
    manager = StateManager()
    
    unsent_ids = manager.get_unsent_cluster_ids()
    
    # Should return IDs 1, 2, 3 (not 4, 5 which are sent)
    assert len(unsent_ids) == 3
    assert 1 in unsent_ids
    assert 2 in unsent_ids
    assert 3 in unsent_ids
    assert 4 not in unsent_ids
    assert 5 not in unsent_ids


def test_archive_old_sent(setup_test_db):
    """Test archiving old sent content"""
    manager = StateManager()
    
    # Archive content older than 30 days
    archived_count = manager.archive_old_sent(days=30)
    
    # Should archive cluster ID 5 (35 days old)
    assert archived_count == 1
    
    # Verify database update
    conn = sqlite3.connect(setup_test_db)
    conn.row_factory = sqlite3.Row
    
    cluster5 = conn.execute("SELECT * FROM clusters WHERE id = 5").fetchone()
    assert cluster5['included_in_digest'] == 2  # Archived status
    
    # Cluster 4 (1 day old) should still be status 1
    cluster4 = conn.execute("SELECT * FROM clusters WHERE id = 4").fetchone()
    assert cluster4['included_in_digest'] == 1  # Still "sent" status
    
    conn.close()


def test_archive_old_sent_no_old_content(setup_test_db):
    """Test archiving when no old content exists"""
    manager = StateManager()
    
    # Archive content older than 100 days (none exist)
    archived_count = manager.archive_old_sent(days=100)
    assert archived_count == 0


def test_get_sent_stats(setup_test_db):
    """Test getting sent content statistics"""
    manager = StateManager()
    
    # Get stats for last 7 days
    stats = manager.get_sent_stats(days=7)
    
    # Should include cluster 4 (sent yesterday)
    assert stats['total_sent'] >= 1
    assert stats['digests_count'] >= 1
    assert stats['lookback_days'] == 7
    assert stats['last_digest_id'] is not None


def test_reset_sent_status_specific_clusters(setup_test_db):
    """Test resetting specific cluster sent status"""
    manager = StateManager()
    
    # Reset cluster 4 (currently sent)
    reset_count = manager.reset_sent_status(cluster_ids=[4])
    assert reset_count == 1
    
    # Verify database update
    conn = sqlite3.connect(setup_test_db)
    conn.row_factory = sqlite3.Row
    
    cluster4 = conn.execute("SELECT * FROM clusters WHERE id = 4").fetchone()
    assert cluster4['sent_at'] is None
    assert cluster4['digest_id'] is None
    assert cluster4['included_in_digest'] == 0
    
    conn.close()


def test_reset_sent_status_all_clusters(setup_test_db):
    """Test resetting all sent clusters"""
    manager = StateManager()
    
    # Reset all sent clusters
    reset_count = manager.reset_sent_status(cluster_ids=None)
    
    # Should reset clusters 4 and 5
    assert reset_count == 2
    
    # Verify database updates
    conn = sqlite3.connect(setup_test_db)
    conn.row_factory = sqlite3.Row
    
    sent_clusters = conn.execute(
        "SELECT COUNT(*) as count FROM clusters WHERE sent_at IS NOT NULL"
    ).fetchone()
    
    assert sent_clusters['count'] == 0  # All reset
    
    conn.close()


def test_duplicate_prevention_across_runs(setup_test_db):
    """
    Integration test: Verify running pipeline twice shows different stories
    This is the key acceptance criteria for Task 1.3
    """
    manager = StateManager()
    
    # Simulate first run
    conn = sqlite3.connect(setup_test_db)
    conn.row_factory = sqlite3.Row
    
    # Get unsent clusters (should get 1, 2, 3)
    first_run_clusters = conn.execute("""
        SELECT id FROM clusters 
        WHERE sent_at IS NULL 
        ORDER BY importance_score DESC
    """).fetchall()
    
    first_run_ids = [c['id'] for c in first_run_clusters]
    assert len(first_run_ids) == 3
    assert first_run_ids == [3, 1, 2]  # Ordered by importance_score DESC
    
    # Mark as sent
    manager.mark_as_sent(first_run_ids, "2026-08-08-run1")
    
    # Simulate second run - should get NO clusters (all sent)
    second_run_clusters = conn.execute("""
        SELECT id FROM clusters 
        WHERE sent_at IS NULL 
        ORDER BY importance_score DESC
    """).fetchall()
    
    second_run_ids = [c['id'] for c in second_run_clusters]
    assert len(second_run_ids) == 0  # All clusters already sent
    
    conn.close()
    
    print("\n✅ DUPLICATE PREVENTION TEST PASSED")
    print("First run: 3 clusters sent")
    print("Second run: 0 clusters (all already sent)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
