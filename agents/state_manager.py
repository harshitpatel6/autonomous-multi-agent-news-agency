"""
State Manager: Tracks sent content and prevents duplicates across runs
Part of the Autonomous AI News Agency system
"""
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import sqlite3


def _get_db_connection():
    """Get database connection using config.DB_PATH"""
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class StateManager:
    """
    Manages sent content tracking to prevent duplicates across pipeline runs.
    
    Responsibilities:
    - Mark clusters as sent after digest generation
    - Filter out already-sent clusters from new runs
    - Archive old sent content for historical tracking
    - Provide metrics on sent content
    """
    
    def __init__(self):
        """Initialize StateManager with database connection"""
        pass  # Connection created per-method for thread safety
    
    def mark_as_sent(self, cluster_ids: List[int], digest_id: str) -> int:
        """
        Mark clusters as sent in the current digest.
        
        Args:
            cluster_ids: List of cluster IDs that were included in digest
            digest_id: Unique identifier for this digest (e.g., "2026-08-08-daily")
        
        Returns:
            Number of clusters marked as sent
        
        Updates:
            - sent_at: Current UTC timestamp
            - digest_id: ID of the digest that included this cluster
            - included_in_digest: Set to 1 (sent)
        """
        if not cluster_ids:
            return 0
        
        now = datetime.now(timezone.utc).isoformat()
        conn = _get_db_connection()
        
        try:
            conn.executemany(
                """UPDATE clusters 
                   SET sent_at = ?, digest_id = ?, included_in_digest = 1
                   WHERE id = ?""",
                [(now, digest_id, cid) for cid in cluster_ids]
            )
            conn.commit()
            updated = conn.total_changes
            print(f"✓ Marked {updated} clusters as sent (digest: {digest_id})")
            return updated
        except Exception as e:
            print(f"✗ Error marking clusters as sent: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()
    
    def filter_unsent_clusters(self, clusters: List[Dict]) -> List[Dict]:
        """
        Remove already-sent clusters from the list.
        
        Args:
            clusters: List of cluster dictionaries with 'id' field
        
        Returns:
            List of clusters that have NOT been sent yet (sent_at IS NULL)
        
        This ensures running the pipeline multiple times shows different stories.
        """
        if not clusters:
            return []
        
        # Filter clusters where sent_at is None (not yet sent)
        unsent = [c for c in clusters if c.get('sent_at') is None]
        
        sent_count = len(clusters) - len(unsent)
        if sent_count > 0:
            print(f"✓ Filtered out {sent_count} already-sent clusters")
        
        return unsent
    
    def get_unsent_cluster_ids(self) -> List[int]:
        """
        Get IDs of all clusters that haven't been sent yet.
        
        Returns:
            List of cluster IDs where sent_at IS NULL
        
        Useful for queries that need to explicitly fetch only unsent clusters.
        """
        conn = _get_db_connection()
        try:
            rows = conn.execute(
                """SELECT id FROM clusters 
                   WHERE sent_at IS NULL 
                   ORDER BY created_at DESC"""
            ).fetchall()
            return [row['id'] for row in rows]
        finally:
            conn.close()
    
    def archive_old_sent(self, days: int = 30) -> int:
        """
        Archive sent content older than N days.
        
        Args:
            days: Age threshold in days (default: 30)
        
        Returns:
            Number of clusters archived
        
        Archives by setting included_in_digest = 2 (archived status).
        This keeps the data but marks it as historical.
        
        Status codes:
        - 0: Not sent
        - 1: Sent (recent)
        - 2: Archived (old sent content)
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = _get_db_connection()
        
        try:
            cursor = conn.execute(
                """UPDATE clusters SET included_in_digest = 2
                   WHERE sent_at < ? AND included_in_digest = 1""",
                (cutoff,)
            )
            conn.commit()
            archived = cursor.rowcount
            
            if archived > 0:
                print(f"✓ Archived {archived} clusters older than {days} days")
            
            return archived
        except Exception as e:
            print(f"✗ Error archiving old content: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()
    
    def get_sent_stats(self, days: int = 7) -> Dict:
        """
        Get statistics on sent content for the last N days.
        
        Args:
            days: Lookback window in days (default: 7)
        
        Returns:
            Dictionary with metrics:
            - total_sent: Total clusters sent in period
            - digests_count: Number of digests generated
            - avg_stories_per_digest: Average stories per digest
            - last_digest_id: Most recent digest ID
            - last_sent_at: Most recent send timestamp
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = _get_db_connection()
        
        try:
            # Get overall stats
            stats_row = conn.execute(
                """SELECT 
                    COUNT(*) as total_sent,
                    COUNT(DISTINCT digest_id) as digests_count,
                    MAX(sent_at) as last_sent_at,
                    MAX(digest_id) as last_digest_id
                FROM clusters
                WHERE sent_at >= ? AND included_in_digest = 1""",
                (cutoff,)
            ).fetchone()
            
            total_sent = stats_row['total_sent'] or 0
            digests_count = stats_row['digests_count'] or 0
            
            stats = {
                'total_sent': total_sent,
                'digests_count': digests_count,
                'avg_stories_per_digest': round(total_sent / digests_count, 1) if digests_count > 0 else 0,
                'last_sent_at': stats_row['last_sent_at'],
                'last_digest_id': stats_row['last_digest_id'],
                'lookback_days': days
            }
            
            return stats
        finally:
            conn.close()
    
    def reset_sent_status(self, cluster_ids: Optional[List[int]] = None) -> int:
        """
        Reset sent status for testing purposes.
        
        Args:
            cluster_ids: Optional list of specific cluster IDs to reset.
                        If None, resets ALL clusters (use with caution!)
        
        Returns:
            Number of clusters reset
        
        ⚠️ WARNING: This is for TESTING ONLY. Use cautiously in production.
        Resets sent_at, digest_id, and included_in_digest to allow re-sending.
        """
        conn = _get_db_connection()
        
        try:
            if cluster_ids:
                placeholders = ','.join('?' * len(cluster_ids))
                cursor = conn.execute(
                    f"""UPDATE clusters 
                       SET sent_at = NULL, digest_id = NULL, included_in_digest = 0
                       WHERE id IN ({placeholders})""",
                    cluster_ids
                )
            else:
                # Reset ALL - dangerous operation
                cursor = conn.execute(
                    """UPDATE clusters 
                       SET sent_at = NULL, digest_id = NULL, included_in_digest = 0
                       WHERE included_in_digest IN (1, 2)"""
                )
            
            conn.commit()
            reset_count = cursor.rowcount
            
            if cluster_ids:
                print(f"⚠️  Reset {reset_count} specific clusters for testing")
            else:
                print(f"⚠️  Reset ALL {reset_count} clusters for testing")
            
            return reset_count
        except Exception as e:
            print(f"✗ Error resetting sent status: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()
