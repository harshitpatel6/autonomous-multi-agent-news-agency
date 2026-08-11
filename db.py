"""
SQLite setup for Autonomous AI News Agency
Includes state management, observability, and multi-agent support
"""
import sqlite3
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    summary_raw TEXT,
    full_text TEXT,
    published_at TEXT,
    fetched_at TEXT NOT NULL,
    cluster_id INTEGER,
    FOREIGN KEY (cluster_id) REFERENCES clusters(id)
);

CREATE TABLE IF NOT EXISTS clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    headline TEXT,
    category TEXT,
    summary TEXT,
    importance_score INTEGER,
    included_in_digest INTEGER DEFAULT 0,
    sent_at TEXT,
    digest_id TEXT,
    quality_score REAL,
    backup_used INTEGER DEFAULT 0,
    validation_status TEXT,
    fact_check_score REAL,
    full_content TEXT,
    key_takeaways TEXT,
    published_at TEXT,
    seo_title TEXT,
    seo_description TEXT,
    seo_keywords TEXT,
    seo_score REAL,
    seo_audited_at TEXT
);

CREATE TABLE IF NOT EXISTS digests (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    mode TEXT NOT NULL,
    story_count INTEGER NOT NULL,
    recipient_count INTEGER DEFAULT 0,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    action TEXT NOT NULL,
    input_data TEXT,
    output_data TEXT,
    success INTEGER NOT NULL,
    error_message TEXT,
    execution_time_ms INTEGER
);

CREATE TABLE IF NOT EXISTS digest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sent_at TEXT NOT NULL,
    recipient TEXT NOT NULL,
    cluster_ids TEXT NOT NULL
);

-- Persisted circuit-breaker state (utils/error_handling.py), keyed by provider
-- ("claude"/"groq"/"gemini"). Lets a fresh publish.py process (a new one spawns
-- every 15 min via launchd) know a provider is still cooling down from a quota
-- error in the *previous* process, instead of re-discovering it from scratch.
CREATE TABLE IF NOT EXISTS provider_state (
    service TEXT PRIMARY KEY,
    opened_at REAL NOT NULL,
    cooldown_seconds INTEGER NOT NULL
);

-- One row per publish.py run (every 15 min), so the dashboard can show *why*
-- throughput was low on a given cycle instead of just that it was low.
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    new_articles INTEGER DEFAULT 0,
    old_articles_filtered INTEGER DEFAULT 0,
    feed_errors INTEGER DEFAULT 0,
    clusters_pending INTEGER DEFAULT 0,
    clusters_summarized_ok INTEGER DEFAULT 0,
    clusters_summarized_failed INTEGER DEFAULT 0,
    publish_candidates INTEGER DEFAULT 0,
    published_count INTEGER DEFAULT 0,
    published_ids TEXT,
    error_summary TEXT
);

-- SEO Agent (agents/seo_agent.py): one row per site-wide audit sweep, so the
-- dashboard can show a score trend over time instead of just a current snapshot.
CREATE TABLE IF NOT EXISTS seo_audit_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    articles_checked INTEGER DEFAULT 0,
    avg_score REAL,
    issues_found INTEGER DEFAULT 0,
    trend REAL,
    summary TEXT
);

-- Current issues per article (replaced wholesale on every re-audit of that
-- article, not accumulated) - what's actionable right now, per page.
CREATE TABLE IF NOT EXISTS seo_page_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_id INTEGER NOT NULL,
    severity TEXT NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    FOREIGN KEY (cluster_id) REFERENCES clusters(id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_clusters_sent_at ON clusters(sent_at);
CREATE INDEX IF NOT EXISTS idx_clusters_digest_id ON clusters(digest_id);
CREATE INDEX IF NOT EXISTS idx_clusters_validation_status ON clusters(validation_status);
CREATE INDEX IF NOT EXISTS idx_clusters_published_at ON clusters(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_cluster_id ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_agent_logs_timestamp ON agent_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_agent_logs_agent_name ON agent_logs(agent_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at ON pipeline_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_seo_audit_runs_run_at ON seo_audit_runs(run_at);
CREATE INDEX IF NOT EXISTS idx_seo_page_issues_cluster_id ON seo_page_issues(cluster_id);
"""


def get_connection():
    """Get database connection with row factory"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database with schema"""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
