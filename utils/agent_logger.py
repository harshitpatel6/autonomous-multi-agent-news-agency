"""
Structured logging for agent actions (Task 3.1)
All agent activity is persisted to the agent_logs table for observability.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

DEBUG, INFO, WARNING, ERROR = "DEBUG", "INFO", "WARNING", "ERROR"


def _get_conn():
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_json(data: Any) -> Optional[str]:
    if data is None:
        return None
    try:
        return json.dumps(data, default=str)[:4000]
    except Exception:
        return str(data)[:4000]


class AgentLogger:
    """Writes and queries structured agent activity logs."""

    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    def log_action(
        self,
        action: str,
        input_data: Any = None,
        output_data: Any = None,
        success: bool = True,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        level: str = INFO,
    ) -> None:
        """Persist one agent action to agent_logs. Never raises."""
        try:
            conn = _get_conn()
            conn.execute(
                """INSERT INTO agent_logs
                   (timestamp, agent_name, action, input_data, output_data, success, error_message, execution_time_ms, pid)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now(timezone.utc).isoformat(),
                    self.agent_name,
                    action,
                    _safe_json(input_data),
                    _safe_json(output_data),
                    1 if success else 0,
                    error_message,
                    execution_time_ms,
                    os.getpid(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            # Logging must never break the pipeline
            print(f"⚠️  AgentLogger failed to persist log for {self.agent_name}.{action}: {e}")

        prefix = {DEBUG: "🔍", INFO: "ℹ️", WARNING: "⚠️", ERROR: "❌"}.get(level, "•")
        if level != DEBUG:
            print(f"{prefix} [{self.agent_name}] {action} — {'ok' if success else 'FAILED'}"
                  + (f" ({execution_time_ms}ms)" if execution_time_ms is not None else ""))


def query_recent_logs(agent_name: Optional[str] = None, limit: int = 50) -> List[Dict]:
    conn = _get_conn()
    if agent_name:
        rows = conn.execute(
            "SELECT * FROM agent_logs WHERE agent_name = ? ORDER BY id DESC LIMIT ?",
            (agent_name, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM agent_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_failures(hours: int = 24, limit: int = 50) -> List[Dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM agent_logs WHERE success = 0 AND timestamp >= ? ORDER BY id DESC LIMIT ?",
        (cutoff, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_agent_success_rate(agent_name: str, hours: int = 24) -> Dict:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    conn = _get_conn()
    row = conn.execute(
        """SELECT COUNT(*) as total, SUM(success) as successes,
                  AVG(execution_time_ms) as avg_ms
           FROM agent_logs WHERE agent_name = ? AND timestamp >= ?""",
        (agent_name, cutoff),
    ).fetchone()
    conn.close()
    total = row["total"] or 0
    successes = row["successes"] or 0
    return {
        "agent_name": agent_name,
        "total_actions": total,
        "success_count": successes,
        "success_rate": round(successes / total, 3) if total else None,
        "avg_execution_ms": round(row["avg_ms"], 1) if row["avg_ms"] else None,
        "window_hours": hours,
    }
