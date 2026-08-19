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
    image_url TEXT,
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
    seo_audited_at TEXT,
    -- Lead image for the site card/hero, chosen at publish time (agents/writer_agent.py)
    -- from whichever of this cluster's source articles has one (see utils/fulltext.py).
    -- image_credit/image_credit_url identify the original publisher for the "Photo: X"
    -- caption - we hotlink rather than re-host, so attribution matters.
    image_url TEXT,
    image_credit TEXT,
    image_credit_url TEXT
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
    execution_time_ms INTEGER,
    pid INTEGER
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

-- Insights desk (agents/insight_agent.py): original, non-news editorial content
-- (explainers, research roundups, weekly synthesis, opinion, fun/creative formats).
-- Deliberately its own table, not `clusters` - see config.py's "Insights desk" comment
-- for why reusing the news schema here would have recreated the over-extraction bug
-- this whole migration exists to fix.
CREATE TABLE IF NOT EXISTS features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    published_at TEXT,
    format TEXT NOT NULL,          -- 'roundup' | 'explainer' | 'weekly_synthesis' | 'opinion' | 'fun'
    title TEXT,
    teaser TEXT,
    body_html TEXT,
    sources TEXT,                  -- JSON [{name,url}] - inspiration links, if any (roundup/explainer/synthesis)
    tags TEXT,                     -- JSON string[]
    similarity_score REAL,
    generation_attempts INTEGER DEFAULT 0
);

-- Small generic key/value store for AI-decided, persisted-once site config - currently
-- just the Insights desk's self-chosen name/tagline/mission (agents/insight_agent.py's
-- get_or_create_brand), so the frontend never hardcodes a name a human picked for it.
CREATE TABLE IF NOT EXISTS site_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
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
CREATE INDEX IF NOT EXISTS idx_features_published_at ON features(published_at);
CREATE INDEX IF NOT EXISTS idx_features_format ON features(format);
"""


def get_connection():
    """Get database connection with row factory.

    busy_timeout: the site publish.py cron (every 15 min) and the API server (e.g. a
    manual "Re-process" click from the admin UI, see api/main.py) now both write to
    `clusters` on their own schedules instead of one process owning it exclusively.
    SQLite serializes writers at the file level; without a busy_timeout, a request
    that lands mid-write from the other process fails immediately with "database is
    locked" instead of just waiting the (usually sub-second) moment for the lock to
    clear.
    """
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


# Columns added after the original CREATE TABLE shipped. "CREATE TABLE IF NOT EXISTS"
# is a no-op on a DB that already has the `clusters` table, so new columns need an
# explicit ALTER TABLE migration here or every pre-existing digest.db silently lacks
# them forever. (publish_attempts/last_publish_attempt_at back the retry cap in
# publish.py::publish_ready_clusters - without them a cluster that keeps failing
# Writer/defamation-check gets retried by the full LLM pipeline every 15-min cycle
# forever instead of giving up after MAX_PUBLISH_ATTEMPTS.)
_CLUSTER_COLUMN_MIGRATIONS = [
    ("publish_attempts", "INTEGER DEFAULT 0"),
    ("last_publish_attempt_at", "TEXT"),
    # Summarize-stage retry tracking (mirrors publish_attempts above) - backs the
    # MAX_AUTO_SUMMARIZE_ATTEMPTS cap in summarize.py and the "Re-process" button on
    # the admin Processing History page (see api/main.py::list_failed_clusters /
    # reprocess_cluster_endpoint). summarize_error holds the last failure's reason so
    # the UI can show *why* without anyone having to grep agent_logs.
    ("summarize_attempts", "INTEGER DEFAULT 0"),
    ("last_summarize_attempt_at", "TEXT"),
    ("summarize_error", "TEXT"),
    # Originality guardrail (utils/similarity.py, added 2026-08-15 - see config.py's
    # SIMILARITY_* comment for the article-537 backstory). content_type ("news" or
    # "tutorial_or_reference") is classified by the Reporter Agent alongside headline/
    # category/summary and drives which Writer prompt mode agents/writer_agent.py uses.
    # similarity_score/originality_attempts record the *last* Writer attempt's outcome
    # (score is the best/lowest achieved before either passing or exhausting
    # MAX_ORIGINALITY_REWRITE_ATTEMPTS) for the admin UI - a story is only ever
    # published at all if that attempt passed the strict gate, so there is no
    # "published but flagged" state to surface; this is purely observability.
    ("content_type", "TEXT"),
    ("similarity_score", "REAL"),
    ("originality_attempts", "INTEGER DEFAULT 0"),
]


def _migrate(conn):
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(clusters)")}
    for name, coltype in _CLUSTER_COLUMN_MIGRATIONS:
        if name not in existing:
            conn.execute(f"ALTER TABLE clusters ADD COLUMN {name} {coltype}")

    # pid (added 2026-08-15): which OS process wrote each agent_logs row. Without it,
    # publish.py::summarize_run_errors can only scope "this run's errors" by a
    # timestamp window - and any other script sharing this DB (rewrite_at_risk_articles.py,
    # insights.py, a manually-run digest.py) that happens to call an Agent while a publish.py
    # cycle's window is open gets its failures silently folded into that cycle's "Top
    # errors" on the Processing History page, even when that cycle had zero real
    # candidates of its own. Scoping by pid instead of just time fixes that misattribution.
    agent_logs_cols = {row["name"] for row in conn.execute("PRAGMA table_info(agent_logs)")}
    if "pid" not in agent_logs_cols:
        conn.execute("ALTER TABLE agent_logs ADD COLUMN pid INTEGER")


def init_db():
    """Initialize database with schema"""
    conn = get_connection()
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    conn.close()
