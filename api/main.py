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
def list_articles(limit: int = 30, offset: int = 0, category: Optional[str] = None):
    """Published stories for the public site's article list, newest first.

    Gated on published_at (set by publish.py the moment a story clears QA/Fact-Check),
    not sent_at (which only tracks the twice-daily email digest) - the site goes live
    independently of and ahead of the email. `offset` supports pagination (e.g. the
    admin history tab) without changing the default behavior for existing callers.
    """
    conn = get_connection()
    query = """SELECT id, headline, category, summary, importance_score, published_at,
                      image_url, image_credit
               FROM clusters WHERE published_at IS NOT NULL"""
    params: list = []
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY published_at DESC LIMIT ? OFFSET ?"
    params.append(limit)
    params.append(offset)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/articles/count")
def count_articles(category: Optional[str] = None):
    """Total published-story count, for paginating the admin history tab."""
    conn = get_connection()
    query = "SELECT COUNT(*) as total FROM clusters WHERE published_at IS NOT NULL"
    params: list = []
    if category:
        query += " AND category = ?"
        params.append(category)
    total = conn.execute(query, params).fetchone()["total"]
    conn.close()
    return {"total": total}


@app.get("/api/pipeline/runs")
def list_pipeline_runs(limit: int = 20):
    """Recent publish.py runs with per-stage counts and top error reasons, so the
    dashboard can answer 'why did only N stories publish this cycle' directly instead
    of requiring someone to grep publish.log."""
    import json as _json

    conn = get_connection()
    rows = conn.execute(
        """SELECT id, started_at, finished_at, new_articles, old_articles_filtered, feed_errors,
                  clusters_pending, clusters_summarized_ok, clusters_summarized_failed,
                  publish_candidates, published_count, published_ids, error_summary
           FROM pipeline_runs ORDER BY started_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        d["published_ids"] = _json.loads(d["published_ids"]) if d["published_ids"] else []
        d["error_summary"] = _json.loads(d["error_summary"]) if d["error_summary"] else []
        result.append(d)
    return result


@app.get("/api/articles/{article_id}")
def get_article(article_id: int):
    """Full article detail: headline, full body, and the original sources it was built from."""
    conn = get_connection()
    cluster = conn.execute(
        """SELECT id, headline, category, summary, full_content, key_takeaways, importance_score,
                  published_at, seo_title, seo_description, seo_keywords,
                  image_url, image_credit, image_credit_url
           FROM clusters WHERE id = ? AND published_at IS NOT NULL""",
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
        """SELECT id, headline, category, published_at, image_url, image_credit FROM clusters
           WHERE category = ? AND id != ? AND published_at IS NOT NULL
           ORDER BY published_at DESC LIMIT 4""",
        (cluster["category"], article_id),
    ).fetchall()
    conn.close()

    import json as _json

    result = dict(cluster)
    try:
        result["key_takeaways"] = _json.loads(result["key_takeaways"]) if result["key_takeaways"] else []
    except (TypeError, ValueError):
        result["key_takeaways"] = []
    result["sources"] = [dict(s) for s in sources]
    result["related"] = [dict(r) for r in related]
    return result


# ---------------------------------------------------------------------------
# SEO Agent (agents/seo_agent.py)
# ---------------------------------------------------------------------------
@app.get("/api/seo/overview")
def seo_overview(runs: int = 14):
    """Score trend over the last N audit sweeps, plus the most recent site-wide issues."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, run_at, articles_checked, avg_score, issues_found, trend, summary
           FROM seo_audit_runs ORDER BY run_at DESC LIMIT ?""",
        (runs,),
    ).fetchall()

    total = conn.execute("SELECT COUNT(*) AS n FROM clusters WHERE published_at IS NOT NULL").fetchone()["n"]
    audited = conn.execute(
        "SELECT COUNT(*) AS n FROM clusters WHERE published_at IS NOT NULL AND seo_audited_at IS NOT NULL"
    ).fetchone()["n"]
    conn.close()

    import json as _json
    history = []
    latest_site_issues: list = []
    for r in rows:
        d = dict(r)
        summary = _json.loads(d.pop("summary")) if d.get("summary") else {}
        if not latest_site_issues:
            latest_site_issues = summary.get("site_issues", [])
        history.append(d)

    return {
        "runs": history,
        "latest_site_issues": latest_site_issues,
        "articles_total": total,
        "articles_audited": audited,
        "articles_pending": max(0, total - audited),
    }


@app.get("/api/seo/pages")
def seo_pages(limit: int = 50, only_issues: bool = False):
    """Per-article SEO snapshot for the admin table: score, meta, and current issues."""
    conn = get_connection()
    query = """SELECT id, headline, category, seo_title, seo_description, seo_score, seo_audited_at
               FROM clusters WHERE published_at IS NOT NULL"""
    if only_issues:
        query += " AND (seo_score IS NULL OR seo_score < 100)"
    query += " ORDER BY (seo_score IS NULL), seo_score ASC LIMIT ?"
    rows = conn.execute(query, (limit,)).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        issues = conn.execute(
            "SELECT severity, code, message FROM seo_page_issues WHERE cluster_id = ? ORDER BY severity",
            (d["id"],),
        ).fetchall()
        d["issues"] = [dict(i) for i in issues]
        result.append(d)
    conn.close()
    return result


@app.post("/api/seo/audit")
def seo_audit_now(limit: int = 15):
    """Manual trigger for an audit sweep (dashboard 'Run now' button) - the same
    sweep publish.py already runs automatically every cycle, just on-demand."""
    from agents.seo_agent import seo_agent
    return seo_agent.audit_site(limit=limit)


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
