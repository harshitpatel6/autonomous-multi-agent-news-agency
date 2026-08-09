"""
FastAPI backend for the Web Dashboard (Task 5.4).
Exposes read endpoints for metrics/digests/agent performance, CEO chat/command
endpoints backed by agents.ceo_agent, a config endpoint for digest mode, and a
WebSocket that pushes fresh metrics on an interval for live dashboard updates.

Run: uvicorn api.main:app --reload --port 8000
"""
import asyncio
import sqlite3
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import get_connection
from utils.metrics_collector import MetricsCollector
from utils import mode_state
from agents.ceo_agent import ceo_agent

app = FastAPI(title="AI News Agency Dashboard API", version="1.0.0")

# Dev-friendly CORS. Lock this down to your deployed frontend origin in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

metrics = MetricsCollector()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    question: str


class CommandRequest(BaseModel):
    command: str


class ModeRequest(BaseModel):
    mode: str  # "daily" | "weekly"


# ---------------------------------------------------------------------------
# Metrics & performance
# ---------------------------------------------------------------------------
@app.get("/api/metrics")
def get_metrics(hours: int = 24, days: int = 7):
    return metrics.full_report(hours=hours, days=days)


@app.get("/api/agents/performance")
def get_agent_performance(hours: int = 24):
    return metrics.get_agent_performance(hours=hours)


@app.get("/api/health")
def get_api_health(hours: int = 24):
    return metrics.get_api_health(hours=hours)


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------
@app.get("/api/digests")
def get_recent_digests(limit: int = 20):
    conn = get_connection()
    rows = conn.execute(
        """SELECT digest_id, COUNT(*) as story_count, MAX(sent_at) as sent_at
           FROM clusters
           WHERE digest_id IS NOT NULL
           GROUP BY digest_id
           ORDER BY sent_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/digests/{digest_id}")
def get_digest_detail(digest_id: str):
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, headline, category, summary, importance_score, quality_score,
                  fact_check_score, backup_used, sent_at
           FROM clusters WHERE digest_id = ? ORDER BY importance_score DESC""",
        (digest_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Public articles (website)
# ---------------------------------------------------------------------------
@app.get("/api/articles")
def list_articles(limit: int = 30, category: Optional[str] = None):
    """Published stories for the public site's article list, newest first."""
    conn = get_connection()
    query = """SELECT id, headline, category, summary, importance_score, sent_at
               FROM clusters WHERE sent_at IS NOT NULL"""
    params: list = []
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY sent_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/articles/{article_id}")
def get_article(article_id: int):
    """Full article detail: headline, full body, and the original sources it was built from."""
    conn = get_connection()
    cluster = conn.execute(
        """SELECT id, headline, category, summary, full_content, importance_score, sent_at
           FROM clusters WHERE id = ? AND sent_at IS NOT NULL""",
        (article_id,),
    ).fetchone()
    if not cluster:
        conn.close()
        return {"error": "not found"}

    sources = conn.execute(
        "SELECT source, title, url, published_at FROM articles WHERE cluster_id = ?",
        (article_id,),
    ).fetchall()

    related = conn.execute(
        """SELECT id, headline, category, sent_at FROM clusters
           WHERE category = ? AND id != ? AND sent_at IS NOT NULL
           ORDER BY sent_at DESC LIMIT 4""",
        (cluster["category"], article_id),
    ).fetchall()
    conn.close()

    result = dict(cluster)
    result["sources"] = [dict(s) for s in sources]
    result["related"] = [dict(r) for r in related]
    return result


# ---------------------------------------------------------------------------
# CEO Agent
# ---------------------------------------------------------------------------
@app.get("/api/ceo/status")
def ceo_status(detailed: bool = False):
    return {"report": ceo_agent.generate_status_report(detailed=detailed)}


@app.post("/api/ceo/chat")
def ceo_chat(req: ChatRequest):
    return {"answer": ceo_agent.handle_query(req.question)}


@app.post("/api/ceo/command")
def ceo_command(req: CommandRequest):
    return {"response": ceo_agent.handle_strategic_command(req.command)}


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@app.get("/api/config")
def get_config():
    from config import FEEDS, TOP_N_STORIES, LOOKBACK_HOURS
    return {
        "digest_mode": mode_state.get_mode(),
        "feed_count": len(FEEDS),
        "top_n_stories": TOP_N_STORIES,
        "lookback_hours": mode_state.get_lookback_hours(),
        "base_lookback_hours": LOOKBACK_HOURS,
    }


@app.post("/api/config/mode")
def set_config_mode(req: ModeRequest):
    ok = mode_state.set_mode(req.mode)
    if not ok:
        return {"success": False, "error": f"invalid mode '{req.mode}', must be daily|weekly"}
    return {"success": True, "mode": req.mode}


# ---------------------------------------------------------------------------
# Real-time updates
# ---------------------------------------------------------------------------
@app.websocket("/ws/metrics")
async def ws_metrics(websocket: WebSocket, interval_seconds: int = 10):
    """Pushes a fresh metrics snapshot every `interval_seconds` while connected."""
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(metrics.full_report())
            await asyncio.sleep(interval_seconds)
    except WebSocketDisconnect:
        pass
