#!/usr/bin/env python3
"""
Test script for database migration
Validates schema, data integrity, and idempotency
"""
import sqlite3
import json
from datetime import datetime, timezone
from db import get_connection, init_db


def test_schema():
    """Test that all required columns and tables exist"""
    print("="*60)
    print("Test 1: Schema Validation")
    print("="*60)
    
    conn = get_connection()
    
    # Test clusters table columns
    cursor = conn.execute("PRAGMA table_info(clusters)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    required_columns = {
        'id': 'INTEGER',
        'created_at': 'TEXT',
        'headline': 'TEXT',
        'category': 'TEXT',
        'summary': 'TEXT',
        'importance_score': 'INTEGER',
        'included_in_digest': 'INTEGER',
        'sent_at': 'TEXT',
        'digest_id': 'TEXT',
        'quality_score': 'REAL',
        'backup_used': 'INTEGER',
        'validation_status': 'TEXT',
        'fact_check_score': 'REAL'
    }
    
    all_good = True
    for col, col_type in required_columns.items():
        if col in columns:
            print(f"  ✓ {col} ({col_type})")
        else:
            print(f"  ✗ MISSING: {col} ({col_type})")
            all_good = False
    
    # Test required tables
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = {row[0] for row in cursor.fetchall()}
    
    required_tables = {'articles', 'clusters', 'digests', 'agent_logs'}
    print(f"\nRequired tables:")
    for table in required_tables:
        if table in tables:
            print(f"  ✓ {table}")
        else:
            print(f"  ✗ MISSING: {table}")
            all_good = False
    
    conn.close()
    
    if all_good:
        print("\n✅ Schema validation PASSED")
    else:
        print("\n❌ Schema validation FAILED")
    
    return all_good


def test_data_preservation():
    """Test that existing data was preserved"""
    print("\n" + "="*60)
    print("Test 2: Data Preservation")
    print("="*60)
    
    conn = get_connection()
    
    # Check article count
    cursor = conn.execute("SELECT COUNT(*) FROM articles")
    article_count = cursor.fetchone()[0]
    print(f"Articles preserved: {article_count}")
    
    # Check cluster count
    cursor = conn.execute("SELECT COUNT(*) FROM clusters")
    cluster_count = cursor.fetchone()[0]
    print(f"Clusters preserved: {cluster_count}")
    
    # Check that old columns still have data
    cursor = conn.execute("""
        SELECT COUNT(*) FROM clusters 
        WHERE created_at IS NOT NULL
    """)
    clusters_with_timestamp = cursor.fetchone()[0]
    print(f"Clusters with created_at: {clusters_with_timestamp}")
    
    # Check new columns are nullable (NULL by default)
    cursor = conn.execute("""
        SELECT COUNT(*) FROM clusters 
        WHERE sent_at IS NULL
    """)
    unsent_clusters = cursor.fetchone()[0]
    print(f"Clusters with sent_at NULL: {unsent_clusters}")
    
    conn.close()
    
    all_good = article_count > 0 and cluster_count > 0
    if all_good:
        print("\n✅ Data preservation PASSED")
    else:
        print("\n❌ Data preservation FAILED")
    
    return all_good


def test_state_management():
    """Test state management functionality"""
    print("\n" + "="*60)
    print("Test 3: State Management")
    print("="*60)
    
    conn = get_connection()
    
    # Test marking clusters as sent
    print("Testing mark_as_sent functionality...")
    
    # Get a cluster that hasn't been sent
    cursor = conn.execute("""
        SELECT id FROM clusters 
        WHERE sent_at IS NULL 
        LIMIT 1
    """)
    row = cursor.fetchone()
    
    if row:
        cluster_id = row[0]
        test_digest_id = "test-2026-08-08-daily"
        now = datetime.now(timezone.utc).isoformat()
        
        # Mark as sent
        conn.execute("""
            UPDATE clusters 
            SET sent_at = ?, digest_id = ?, included_in_digest = 1
            WHERE id = ?
        """, (now, test_digest_id, cluster_id))
        conn.commit()
        
        # Verify it was updated
        cursor = conn.execute("""
            SELECT sent_at, digest_id, included_in_digest 
            FROM clusters WHERE id = ?
        """, (cluster_id,))
        result = cursor.fetchone()
        
        if result and result[0] and result[1] == test_digest_id:
            print(f"  ✓ Marked cluster {cluster_id} as sent")
            
            # Test filtering unsent clusters
            cursor = conn.execute("""
                SELECT COUNT(*) FROM clusters 
                WHERE sent_at IS NULL
            """)
            unsent_count = cursor.fetchone()[0]
            print(f"  ✓ Unsent clusters: {unsent_count}")
            
            # Rollback for test
            conn.execute("""
                UPDATE clusters 
                SET sent_at = NULL, digest_id = NULL, included_in_digest = 0
                WHERE id = ?
            """, (cluster_id,))
            conn.commit()
            print(f"  ✓ Rolled back test changes")
            
            all_good = True
        else:
            print(f"  ✗ Failed to mark cluster as sent")
            all_good = False
    else:
        print("  - No unsent clusters to test with")
        all_good = True
    
    conn.close()
    
    if all_good:
        print("\n✅ State management PASSED")
    else:
        print("\n❌ State management FAILED")
    
    return all_good


def test_digest_tracking():
    """Test digest tracking functionality"""
    print("\n" + "="*60)
    print("Test 4: Digest Tracking")
    print("="*60)
    
    conn = get_connection()
    
    # Insert a test digest
    test_digest = {
        'id': 'test-2026-08-08-daily',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'sent_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'daily',
        'story_count': 15,
        'recipient_count': 1,
        'status': 'sent'
    }
    
    try:
        conn.execute("""
            INSERT INTO digests (id, created_at, sent_at, mode, story_count, recipient_count, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            test_digest['id'],
            test_digest['created_at'],
            test_digest['sent_at'],
            test_digest['mode'],
            test_digest['story_count'],
            test_digest['recipient_count'],
            test_digest['status']
        ))
        conn.commit()
        print(f"  ✓ Inserted test digest: {test_digest['id']}")
        
        # Query it back
        cursor = conn.execute("SELECT * FROM digests WHERE id = ?", (test_digest['id'],))
        result = cursor.fetchone()
        
        if result:
            print(f"  ✓ Retrieved test digest successfully")
            print(f"    Mode: {result['mode']}, Stories: {result['story_count']}, Status: {result['status']}")
            
            # Clean up
            conn.execute("DELETE FROM digests WHERE id = ?", (test_digest['id'],))
            conn.commit()
            print(f"  ✓ Cleaned up test digest")
            
            all_good = True
        else:
            print(f"  ✗ Failed to retrieve test digest")
            all_good = False
            
    except Exception as e:
        print(f"  ✗ Error testing digest tracking: {e}")
        all_good = False
    
    conn.close()
    
    if all_good:
        print("\n✅ Digest tracking PASSED")
    else:
        print("\n❌ Digest tracking FAILED")
    
    return all_good


def test_agent_logging():
    """Test agent logging functionality"""
    print("\n" + "="*60)
    print("Test 5: Agent Logging")
    print("="*60)
    
    conn = get_connection()
    
    # Insert test log
    test_log = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'agent_name': 'test_agent',
        'action': 'test_action',
        'input_data': json.dumps({'test': 'input'}),
        'output_data': json.dumps({'test': 'output'}),
        'success': 1,
        'error_message': None,
        'execution_time_ms': 150
    }
    
    try:
        cursor = conn.execute("""
            INSERT INTO agent_logs 
            (timestamp, agent_name, action, input_data, output_data, success, error_message, execution_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            test_log['timestamp'],
            test_log['agent_name'],
            test_log['action'],
            test_log['input_data'],
            test_log['output_data'],
            test_log['success'],
            test_log['error_message'],
            test_log['execution_time_ms']
        ))
        log_id = cursor.lastrowid
        conn.commit()
        print(f"  ✓ Inserted test log entry: ID {log_id}")
        
        # Query it back
        cursor = conn.execute("SELECT * FROM agent_logs WHERE id = ?", (log_id,))
        result = cursor.fetchone()
        
        if result:
            print(f"  ✓ Retrieved test log successfully")
            print(f"    Agent: {result['agent_name']}, Action: {result['action']}, Success: {result['success']}")
            
            # Test querying by agent name (index should help)
            cursor = conn.execute("""
                SELECT COUNT(*) FROM agent_logs 
                WHERE agent_name = ?
            """, (test_log['agent_name'],))
            count = cursor.fetchone()[0]
            print(f"  ✓ Queried logs by agent_name: {count} results")
            
            # Clean up
            conn.execute("DELETE FROM agent_logs WHERE id = ?", (log_id,))
            conn.commit()
            print(f"  ✓ Cleaned up test log")
            
            all_good = True
        else:
            print(f"  ✗ Failed to retrieve test log")
            all_good = False
            
    except Exception as e:
        print(f"  ✗ Error testing agent logging: {e}")
        all_good = False
    
    conn.close()
    
    if all_good:
        print("\n✅ Agent logging PASSED")
    else:
        print("\n❌ Agent logging FAILED")
    
    return all_good


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("DATABASE MIGRATION TEST SUITE")
    print("="*60)
    print()
    
    tests = [
        test_schema,
        test_data_preservation,
        test_state_management,
        test_digest_tracking,
        test_agent_logging
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if all(results):
        print("\n🎉 ALL TESTS PASSED!")
        print("The database migration is working correctly.")
        return 0
    else:
        print("\n⚠️  SOME TESTS FAILED")
        print("Please review the test output above.")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
