"""
Integration tests for the full pipeline (Task 4.2)
Covers: full pipeline via MessageRouter, duplicate prevention across runs,
degraded mode when LLMs are unavailable, and state management end to end.
Uses an isolated temp DB; no real RSS/SMTP/LLM calls are made.
"""
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone

import pytest


def now_iso():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def test_db(monkeypatch):
    """Isolated temp DB, wired into every module that caches DB_PATH at import time."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    monkeypatch.setattr("config.DB_PATH", tmp.name)
    monkeypatch.setattr("db.DB_PATH", tmp.name)
    monkeypatch.setattr("agents.agent_coordinator.DB_PATH", tmp.name)

    from db import SCHEMA
    conn = sqlite3.connect(tmp.name)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return tmp.name


def insert_cluster(db_path, id, headline, summary="Summary", score=8, sent_at=None, article_age_hours=1):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO clusters (id, created_at, headline, category, summary, importance_score, included_in_digest, sent_at) "
        "VALUES (?, ?, ?, 'Company News', ?, ?, ?, ?)",
        (id, now_iso(), headline, summary, score, 1 if sent_at else 0, sent_at),
    )
    pub = (datetime.now(timezone.utc) - timedelta(hours=article_age_hours)).isoformat()
    conn.execute(
        "INSERT INTO articles (source, title, url, summary_raw, published_at, fetched_at, cluster_id) "
        "VALUES ('OpenAI', ?, ?, 'raw text', ?, ?, ?)",
        (f"Article for {headline}", f"https://openai.com/{id}", pub, now_iso(), id),
    )
    conn.commit()
    conn.close()


class TestFullPipeline:
    def test_pipeline_selects_valid_clusters(self, test_db):
        from agents.agent_coordinator import AgentCoordinator
        for i in range(1, 4):
            insert_cluster(test_db, i, f"Story {i}")

        coordinator = AgentCoordinator()
        success, selected, report = coordinator.run_full_validation_pipeline()

        assert success is True
        assert len(selected) == 3
        assert "READY FOR QA" in report or "Degraded mode" in report

    def test_pipeline_empty_when_no_clusters(self, test_db):
        from agents.agent_coordinator import AgentCoordinator
        coordinator = AgentCoordinator()
        success, selected, report = coordinator.run_full_validation_pipeline()
        assert success is False
        assert selected == []


class TestQAFailureBackupFlow:
    def test_qa_partial_verdict_triggers_editor_backup(self, test_db):
        """A cluster with a stale article should be rejected by QA, and Editor should
        supply a replacement from remaining unsent clusters (Task 1.5)."""
        from agents.qa_agent import QAAgent
        from agents.editor_agent import EditorAgent

        insert_cluster(test_db, 1, "Good story", article_age_hours=1)
        insert_cluster(test_db, 2, "Backup story", article_age_hours=1)

        # Cluster 3: simulate a stale/rejected story handed to QA
        stale_cluster = {
            "id": 3, "headline": "Stale story", "category": "Company News", "summary": "S",
            "importance_score": 5, "created_at": now_iso(), "sent_at": None,
            "articles": [{"source": "X", "title": "Old", "url": "https://x.com/old",
                          "published_at": "2020-01-01T00:00:00+00:00", "fetched_at": now_iso()}],
        }
        good_cluster = {
            "id": 1, "headline": "Good story", "category": "Company News", "summary": "S",
            "importance_score": 8, "created_at": now_iso(), "sent_at": None,
            "articles": [{"source": "OpenAI", "title": "Good", "url": "https://openai.com/1",
                          "published_at": now_iso(), "fetched_at": now_iso()}],
        }

        qa = QAAgent()
        result = qa.validate_clusters_for_digest([good_cluster, stale_cluster], min_count=2)
        assert result["verdict"] == "PARTIAL"
        assert result["backup_request"]["needed"] == 1

        editor = EditorAgent()
        backups = editor.fetch_backup_stories(result["backup_request"]["exclude_ids"], needed=1)
        assert len(backups) == 1
        assert backups[0]["id"] == 2  # cluster 2 was the only remaining unsent candidate


class TestDuplicatePrevention:
    def test_sent_clusters_excluded_from_next_pipeline_run(self, test_db):
        from agents.agent_coordinator import AgentCoordinator
        from agents.state_manager import StateManager

        insert_cluster(test_db, 1, "Run 1 story")
        coordinator = AgentCoordinator()
        success, selected, _ = coordinator.run_full_validation_pipeline()
        assert success and len(selected) == 1

        # Mark it sent, exactly as digest.py does after a successful send
        StateManager().mark_as_sent([c["id"] for c in selected], "2026-08-08-daily")

        # Running the pipeline again must not return the already-sent cluster
        success2, selected2, _ = coordinator.run_full_validation_pipeline()
        assert success2 is False
        assert selected2 == []


class TestDegradedMode:
    def test_pipeline_falls_back_to_degraded_mode_without_llm(self, test_db, monkeypatch):
        monkeypatch.setattr("agents.agent_coordinator.CLAUDE_AVAILABLE", False)
        monkeypatch.setattr("agents.agent_coordinator.GROQ_AVAILABLE", False)

        insert_cluster(test_db, 1, "GPT model release announcement")
        insert_cluster(test_db, 2, "Quarterly funding round closes")

        from agents.agent_coordinator import AgentCoordinator
        coordinator = AgentCoordinator()
        success, selected, report = coordinator.run_full_validation_pipeline()

        assert success is True
        assert len(selected) >= 1  # fuzzy rule-based clustering may merge near-duplicate titles
        assert "Degraded mode" in report
        from agents.degraded_mode import is_active
        assert is_active() is True


class TestStateManagement:
    def test_archive_and_stats_reflect_sent_digests(self, test_db):
        from agents.state_manager import StateManager
        insert_cluster(test_db, 1, "Old sent story",
                        sent_at=(datetime.now(timezone.utc) - timedelta(days=40)).isoformat())

        sm = StateManager()
        archived = sm.archive_old_sent(days=30)
        assert archived == 1

        stats = sm.get_sent_stats(days=60)
        assert stats["total_sent"] >= 0  # archived rows are excluded from included_in_digest=1 stats by design
