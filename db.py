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
    full_content TEXT
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

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_clusters_sent_at ON clusters(sent_at);
CREATE INDEX IF NOT EXISTS idx_clusters_digest_id ON clusters(digest_id);
CREATE INDEX IF NOT EXISTS idx_clusters_validation_status ON clusters(validation_status);
CREATE INDEX IF NOT EXISTS idx_articles_cluster_id ON articles(cluster_id);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_agent_logs_timestamp ON agent_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_agent_logs_agent_name ON agent_logs(agent_name);
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
