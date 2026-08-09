"""
Metrics Collection System (Task 3.2): agent performance & system health rollups,
built on top of the structured agent_logs / clusters / digests tables.
"""
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, List


def _get_conn():
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class MetricsCollector:
    def get_agent_performance(self, hours: int = 24) -> List[Dict]:
        """Success rate, avg latency, and action count per agent over the window."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        conn = _get_conn()
        rows = conn.execute(
            """SELECT agent_name,
                      COUNT(*) as total_actions,
                      SUM(success) as successes,
                      AVG(execution_time_ms) as avg_ms
               FROM agent_logs
               WHERE timestamp >= ?
               GROUP BY agent_name
               ORDER BY total_actions DESC""",
            (cutoff,),
        ).fetchall()
        conn.close()
        return [
            {
                "agent_name": r["agent_name"],
                "total_actions": r["total_actions"],
                "success_rate": round((r["successes"] or 0) / r["total_actions"], 3) if r["total_actions"] else None,
                "avg_latency_ms": round(r["avg_ms"], 1) if r["avg_ms"] else None,
            }
            for r in rows
        ]

    def get_api_health(self, hours: int = 24) -> Dict:
        """Claude vs Groq call success rates, derived from call_llm[provider] log actions."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        conn = _get_conn()
        rows = conn.execute(
            """SELECT action, COUNT(*) as total, SUM(success) as successes
               FROM agent_logs
               WHERE timestamp >= ? AND action LIKE 'call_llm[%'
               GROUP BY action""",
            (cutoff,),
        ).fetchall()
        conn.close()
        health = {}
        for r in rows:
            provider = r["action"].split("[", 1)[1].rstrip("]")
            health[provider] = {
                "total_calls": r["total"],
                "success_rate": round((r["successes"] or 0) / r["total"], 3) if r["total"] else None,
            }
        return health

    def get_digest_stats(self, days: int = 7) -> Dict:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = _get_conn()
        row = conn.execute(
            """SELECT COUNT(*) as stories, COUNT(DISTINCT digest_id) as digests, MAX(sent_at) as last_sent
               FROM clusters WHERE sent_at >= ?""",
            (cutoff,),
        ).fetchone()
        conn.close()
        digests = row["digests"] or 0
        stories = row["stories"] or 0
        return {
            "digests_sent": digests,
            "stories_sent": stories,
            "avg_stories_per_digest": round(stories / digests, 1) if digests else 0,
            "last_sent": row["last_sent"],
            "window_days": days,
        }

    def get_quality_metrics(self, days: int = 7) -> Dict:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = _get_conn()
        row = conn.execute(
            """SELECT AVG(quality_score) as avg_quality, AVG(fact_check_score) as avg_fact_check,
                      SUM(backup_used) as backups_used, COUNT(*) as total
               FROM clusters WHERE sent_at >= ?""",
            (cutoff,),
        ).fetchone()
        conn.close()
        total = row["total"] or 0
        return {
            "avg_quality_score": round(row["avg_quality"], 2) if row["avg_quality"] else None,
            "avg_fact_check_score": round(row["avg_fact_check"], 2) if row["avg_fact_check"] else None,
            "backup_stories_used": row["backups_used"] or 0,
            "backup_rate": round((row["backups_used"] or 0) / total, 3) if total else 0,
            "window_days": days,
        }

    def full_report(self, hours: int = 24, days: int = 7) -> Dict:
        return {
            "agent_performance": self.get_agent_performance(hours),
            "api_health": self.get_api_health(hours),
            "digest_stats": self.get_digest_stats(days),
            "quality_metrics": self.get_quality_metrics(days),
        }
