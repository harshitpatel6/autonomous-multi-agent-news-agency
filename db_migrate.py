#!/usr/bin/env python3
"""
Database migration script for Autonomous AI News Agency
Adds state management and observability tables/columns

Migration is idempotent - can be run multiple times safely
"""
import sqlite3
import sys
from datetime import datetime, timezone
from config import DB_PATH


def get_column_names(conn, table_name):
    """Get list of column names for a table"""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def table_exists(conn, table_name):
    """Check if a table exists"""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def migrate_clusters_table(conn):
    """Add new columns to clusters table for state management"""
    print("Migrating clusters table...")
    
    existing_columns = get_column_names(conn, 'clusters')
    columns_to_add = {
        'sent_at': 'TEXT',
        'digest_id': 'TEXT',
        'quality_score': 'REAL',
        'backup_used': 'INTEGER DEFAULT 0',
        'validation_status': 'TEXT',
        'fact_check_score': 'REAL',
        'full_content': 'TEXT',
        'key_takeaways': 'TEXT',
        'published_at': 'TEXT'
    }
    
    added_count = 0
    for column_name, column_type in columns_to_add.items():
        if column_name not in existing_columns:
            try:
                conn.execute(f"ALTER TABLE clusters ADD COLUMN {column_name} {column_type}")
                print(f"  ✓ Added column: {column_name}")
                added_count += 1
            except sqlite3.OperationalError as e:
                print(f"  ✗ Error adding {column_name}: {e}")
        else:
            print(f"  - Column already exists: {column_name}")
    
    if added_count > 0:
        conn.commit()
        print(f"Added {added_count} new columns to clusters table")
    else:
        print("No new columns needed for clusters table")
    
    return added_count


def migrate_articles_table(conn):
    """Add full_text/image_url columns to articles table (see utils/fulltext.py)"""
    print("Migrating articles table...")

    existing_columns = get_column_names(conn, 'articles')
    columns_to_add = {
        'full_text': 'TEXT',
        'image_url': 'TEXT',
    }

    added_count = 0
    for column_name, column_type in columns_to_add.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE articles ADD COLUMN {column_name} {column_type}")
            print(f"  ✓ Added column: {column_name}")
            added_count += 1
        else:
            print(f"  - Column already exists: {column_name}")

    if added_count > 0:
        conn.commit()
    return added_count


def migrate_image_columns(conn):
    """Add lead-image columns to clusters table (agents/writer_agent.py picks these at
    publish time from the cluster's source articles - see utils/fulltext.py)."""
    print("Migrating clusters table for images...")

    existing_columns = get_column_names(conn, 'clusters')
    columns_to_add = {
        'image_url': 'TEXT',
        'image_credit': 'TEXT',
        'image_credit_url': 'TEXT',
    }

    added_count = 0
    for column_name, column_type in columns_to_add.items():
        if column_name not in existing_columns:
            try:
                conn.execute(f"ALTER TABLE clusters ADD COLUMN {column_name} {column_type}")
                print(f"  ✓ Added column: {column_name}")
                added_count += 1
            except sqlite3.OperationalError as e:
                print(f"  ✗ Error adding {column_name}: {e}")
        else:
            print(f"  - Column already exists: {column_name}")

    if added_count > 0:
        conn.commit()
        print(f"Added {added_count} new image columns to clusters table")
    else:
        print("No new image columns needed for clusters table")

    return added_count


def migrate_seo_columns(conn):
    """Add SEO Agent columns to the clusters table (agents/seo_agent.py)"""
    print("Migrating clusters table for SEO Agent...")

    existing_columns = get_column_names(conn, 'clusters')
    columns_to_add = {
        'seo_title': 'TEXT',
        'seo_description': 'TEXT',
        'seo_keywords': 'TEXT',
        'seo_score': 'REAL',
        'seo_audited_at': 'TEXT',
    }

    added_count = 0
    for column_name, column_type in columns_to_add.items():
        if column_name not in existing_columns:
            try:
                conn.execute(f"ALTER TABLE clusters ADD COLUMN {column_name} {column_type}")
                print(f"  ✓ Added column: {column_name}")
                added_count += 1
            except sqlite3.OperationalError as e:
                print(f"  ✗ Error adding {column_name}: {e}")
        else:
            print(f"  - Column already exists: {column_name}")

    if added_count > 0:
        conn.commit()
        print(f"Added {added_count} new SEO columns to clusters table")
    else:
        print("No new SEO columns needed for clusters table")

    return added_count


def create_seo_tables(conn):
    """Create seo_audit_runs + seo_page_issues tables (agents/seo_agent.py)"""
    print("\nCreating SEO Agent tables...")

    created = 0
    if not table_exists(conn, 'seo_audit_runs'):
        conn.execute("""
            CREATE TABLE seo_audit_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at TEXT NOT NULL,
                articles_checked INTEGER DEFAULT 0,
                avg_score REAL,
                issues_found INTEGER DEFAULT 0,
                trend REAL,
                summary TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_seo_audit_runs_run_at ON seo_audit_runs(run_at)")
        print("  ✓ Created seo_audit_runs table")
        created += 1
    else:
        print("  - Table already exists: seo_audit_runs")

    if not table_exists(conn, 'seo_page_issues'):
        conn.execute("""
            CREATE TABLE seo_page_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_id INTEGER NOT NULL,
                severity TEXT NOT NULL,
                code TEXT NOT NULL,
                message TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                FOREIGN KEY (cluster_id) REFERENCES clusters(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_seo_page_issues_cluster_id ON seo_page_issues(cluster_id)")
        print("  ✓ Created seo_page_issues table")
        created += 1
    else:
        print("  - Table already exists: seo_page_issues")

    conn.commit()
    return created


def create_digests_table(conn):
    """Create digests table to track each newsletter sent"""
    print("\nCreating digests table...")
    
    if table_exists(conn, 'digests'):
        print("  - Table already exists: digests")
        return False
    
    conn.execute("""
        CREATE TABLE digests (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            sent_at TEXT,
            mode TEXT NOT NULL,
            story_count INTEGER NOT NULL,
            recipient_count INTEGER DEFAULT 0,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    print("  ✓ Created digests table")
    return True


def create_agent_logs_table(conn):
    """Create agent_logs table for observability"""
    print("\nCreating agent_logs table...")
    
    if table_exists(conn, 'agent_logs'):
        print("  - Table already exists: agent_logs")
        return False
    
    conn.execute("""
        CREATE TABLE agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            action TEXT NOT NULL,
            input_data TEXT,
            output_data TEXT,
            success INTEGER NOT NULL,
            error_message TEXT,
            execution_time_ms INTEGER
        )
    """)
    
    # Create indexes for common queries
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_logs_timestamp 
        ON agent_logs(timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_agent_logs_agent_name 
        ON agent_logs(agent_name)
    """)
    
    conn.commit()
    print("  ✓ Created agent_logs table with indexes")
    return True


def create_indexes(conn):
    """Create indexes for better query performance"""
    print("\nCreating indexes...")
    
    indexes = [
        ("idx_clusters_sent_at", "clusters", "sent_at"),
        ("idx_clusters_digest_id", "clusters", "digest_id"),
        ("idx_clusters_validation_status", "clusters", "validation_status"),
        ("idx_clusters_published_at", "clusters", "published_at"),
        ("idx_articles_cluster_id", "articles", "cluster_id"),
        ("idx_articles_published_at", "articles", "published_at"),
    ]
    
    created_count = 0
    for index_name, table_name, column_name in indexes:
        try:
            conn.execute(f"""
                CREATE INDEX IF NOT EXISTS {index_name} 
                ON {table_name}({column_name})
            """)
            print(f"  ✓ Created index: {index_name}")
            created_count += 1
        except sqlite3.OperationalError as e:
            print(f"  - Index may already exist: {index_name}")
    
    conn.commit()
    return created_count


def verify_migration(conn):
    """Verify that migration completed successfully"""
    print("\n" + "="*60)
    print("Verification Report")
    print("="*60)
    
    issues = []
    
    # Check clusters table columns
    clusters_columns = get_column_names(conn, 'clusters')
    required_columns = [
        'sent_at', 'digest_id', 'quality_score',
        'backup_used', 'validation_status', 'fact_check_score', 'published_at'
    ]
    
    print("\nClusters table columns:")
    for col in required_columns:
        if col in clusters_columns:
            print(f"  ✓ {col}")
        else:
            print(f"  ✗ {col} - MISSING")
            issues.append(f"Missing column in clusters: {col}")
    
    # Check tables exist
    print("\nRequired tables:")
    for table in ['articles', 'clusters', 'digests', 'agent_logs']:
        if table_exists(conn, table):
            print(f"  ✓ {table}")
        else:
            print(f"  ✗ {table} - MISSING")
            issues.append(f"Missing table: {table}")
    
    # Count existing data
    print("\nExisting data:")
    cursor = conn.execute("SELECT COUNT(*) FROM articles")
    article_count = cursor.fetchone()[0]
    print(f"  Articles: {article_count}")
    
    cursor = conn.execute("SELECT COUNT(*) FROM clusters")
    cluster_count = cursor.fetchone()[0]
    print(f"  Clusters: {cluster_count}")
    
    cursor = conn.execute("SELECT COUNT(*) FROM digests")
    digest_count = cursor.fetchone()[0]
    print(f"  Digests: {digest_count}")
    
    cursor = conn.execute("SELECT COUNT(*) FROM agent_logs")
    log_count = cursor.fetchone()[0]
    print(f"  Agent Logs: {log_count}")
    
    # Check indexes
    print("\nIndexes:")
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    )
    indexes = [row[0] for row in cursor.fetchall()]
    print(f"  Total indexes created: {len(indexes)}")
    for idx in indexes:
        print(f"    - {idx}")
    
    print("\n" + "="*60)
    if issues:
        print("❌ Migration completed with issues:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("✅ Migration completed successfully!")
        print("   All columns added, tables created, existing data preserved")
        return True


def backup_database():
    """Create a backup of the database before migration"""
    import shutil
    from pathlib import Path
    
    if not Path(DB_PATH).exists():
        print("No existing database to backup")
        return None
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = f"{DB_PATH}.backup_{timestamp}"
    
    try:
        shutil.copy2(DB_PATH, backup_path)
        print(f"✓ Database backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"⚠ Warning: Could not create backup: {e}")
        return None


def main():
    """Main migration function"""
    print("="*60)
    print("Database Migration: Autonomous AI News Agency")
    print("="*60)
    print(f"Database: {DB_PATH}")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    print("="*60)
    
    # Create backup
    print("\n[Step 1] Creating backup...")
    backup_path = backup_database()
    
    # Connect to database
    print("\n[Step 2] Connecting to database...")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        print("  ✓ Connected successfully")
    except Exception as e:
        print(f"  ✗ Failed to connect: {e}")
        sys.exit(1)
    
    try:
        # Run migrations
        print("\n[Step 3] Running migrations...")
        columns_added = migrate_clusters_table(conn)
        articles_columns_added = migrate_articles_table(conn)
        digests_created = create_digests_table(conn)
        logs_created = create_agent_logs_table(conn)
        seo_columns_added = migrate_seo_columns(conn)
        seo_tables_created = create_seo_tables(conn)
        image_columns_added = migrate_image_columns(conn)
        indexes_created = create_indexes(conn)
        
        # Verify migration
        print("\n[Step 4] Verifying migration...")
        success = verify_migration(conn)
        
        # Summary
        print("\n" + "="*60)
        print("Migration Summary")
        print("="*60)
        print(f"Columns added to clusters: {columns_added}")
        print(f"Columns added to articles: {articles_columns_added}")
        print(f"Digests table created: {'Yes' if digests_created else 'Already exists'}")
        print(f"Agent logs table created: {'Yes' if logs_created else 'Already exists'}")
        print(f"SEO columns added to clusters: {seo_columns_added}")
        print(f"SEO tables created: {seo_tables_created}")
        print(f"Image columns added to clusters: {image_columns_added}")
        print(f"Indexes created: {indexes_created}")
        if backup_path:
            print(f"Backup saved to: {backup_path}")
        print("="*60)
        
        if success:
            print("\n✅ Migration completed successfully!")
            print("   The database is ready for the autonomous AI news agency.")
            return 0
        else:
            print("\n⚠ Migration completed with warnings")
            print("   Please review the verification report above.")
            return 1
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
