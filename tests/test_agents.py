"""
Unit tests for all agents (Task 4.1)
QA Agent, Editor Agent, Reporter Agent, Fact-Checker, CEO Agent, State Manager.
LLM calls are mocked (via Agent.call_llm) so tests run without network/API keys.
"""
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from config import ABSOLUTE_CUTOFF_DATE


@pytest.fixture
def test_db(monkeypatch):
    """Fresh temp sqlite DB per test, wired into config.DB_PATH / db.DB_PATH."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    monkeypatch.setattr("config.DB_PATH", tmp.name)
    monkeypatch.setattr("db.DB_PATH", tmp.name)
    from db import SCHEMA
    conn = sqlite3.connect(tmp.name)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return tmp.name


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def make_cluster(id=1, headline="Test", category="Company News", summary="Summary", score=8, articles=None):
    return {
        "id": id, "headline": headline, "category": category, "summary": summary,
        "importance_score": score, "created_at": now_iso(), "sent_at": None,
        "articles": articles if articles is not None else [
            {"source": "OpenAI", "title": "Title A", "url": "https://openai.com/a",
             "published_at": now_iso(), "fetched_at": now_iso()},
        ],
    }


# ---------------------------------------------------------------------------
# QA Agent
# ---------------------------------------------------------------------------
class TestQAAgent:
    def test_validate_clusters_all_pass(self, test_db):
        from agents.qa_agent import QAAgent
        agent = QAAgent()
        clusters = [make_cluster(1), make_cluster(2)]
        result = agent.validate_clusters_for_digest(clusters, min_count=2)
        assert result["verdict"] == "PASS"
        assert len(result["valid_clusters"]) == 2
        assert result["backup_request"] is None

    def test_validate_clusters_partial_requests_backup(self, test_db):
        from agents.qa_agent import QAAgent
        agent = QAAgent()
        good = make_cluster(1)
        bad = make_cluster(2, articles=[{"source": "X", "title": "Old", "url": "https://x.com/y",
                                          "published_at": "2020-01-01T00:00:00+00:00", "fetched_at": now_iso()}])
        result = agent.validate_clusters_for_digest([good, bad], min_count=2)
        assert result["verdict"] == "PARTIAL"
        assert len(result["valid_clusters"]) == 1
        assert result["backup_request"]["needed"] == 1

    def test_validate_clusters_all_fail(self, test_db):
        from agents.qa_agent import QAAgent
        agent = QAAgent()
        bad = make_cluster(1, articles=[])
        result = agent.validate_clusters_for_digest([bad], min_count=1)
        assert result["verdict"] == "FAIL"
        assert result["valid_clusters"] == []


# ---------------------------------------------------------------------------
# Editor Agent
# ---------------------------------------------------------------------------
class TestEditorAgent:
    def test_select_stories_under_target_returns_all(self, test_db):
        from agents.editor_agent import EditorAgent
        agent = EditorAgent()
        clusters = [make_cluster(i) for i in range(3)]
        result = agent.select_stories(clusters, target_count=5)
        assert result == clusters

    def test_select_stories_llm_failure_falls_back_to_scoring(self, test_db, monkeypatch):
        from agents.editor_agent import EditorAgent
        agent = EditorAgent()
        monkeypatch.setattr(agent, "call_llm", lambda *a, **k: None)
        clusters = [make_cluster(i, score=i, category="Company News") for i in range(10)]
        result = agent.select_stories(clusters, target_count=3)
        assert len(result) == 3
        # Fallback is score-sorted descending
        assert result[0]["importance_score"] >= result[-1]["importance_score"]

    def test_fetch_backup_stories(self, test_db):
        from db import get_connection
        conn = get_connection()
        conn.execute(
            "INSERT INTO clusters (id, created_at, headline, category, summary, importance_score, included_in_digest, sent_at) "
            "VALUES (99, ?, 'Backup', 'Other', 'Summary', 5, 0, NULL)", (now_iso(),),
        )
        conn.commit()
        conn.close()

        from agents.editor_agent import EditorAgent
        agent = EditorAgent()
        backups = agent.fetch_backup_stories(exclude_ids=[1, 2], needed=1)
        assert len(backups) == 1
        assert backups[0]["id"] == 99


# ---------------------------------------------------------------------------
# Reporter Agent
# ---------------------------------------------------------------------------
class TestReporterAgent:
    def test_summarize_cluster_success(self, test_db, monkeypatch):
        from agents.reporter_agent import ResearchReporter
        reporter = ResearchReporter()
        fake_response = json.dumps({
            "headline": "New model released", "category": "Research & Models",
            "summary": "A new model was released.", "importance_score": 7,
        })
        monkeypatch.setattr(reporter, "call_llm", lambda *a, **k: fake_response)
        result = reporter.summarize_cluster([{"source": "arXiv", "title": "Paper", "summary_raw": "..."}])
        assert result["headline"] == "New model released"
        assert result["importance_score"] == 7

    def test_summarize_cluster_empty_articles_returns_none(self, test_db):
        from agents.reporter_agent import GeneralReporter
        reporter = GeneralReporter()
        assert reporter.summarize_cluster([]) is None

    def test_get_reporter_for_category_routes_correctly(self, test_db):
        from agents.reporter_agent import get_reporter_for_category, ResearchReporter, GeneralReporter
        assert isinstance(get_reporter_for_category("Research & Models"), ResearchReporter)
        assert isinstance(get_reporter_for_category("Something Unknown"), GeneralReporter)


# ---------------------------------------------------------------------------
# Fact-Checker Agent
# ---------------------------------------------------------------------------
class TestFactCheckerAgent:
    def test_validate_cluster_high_confidence(self, test_db):
        from agents.fact_checker_agent import FactCheckerAgent
        agent = FactCheckerAgent()
        cluster = make_cluster(1)
        articles = [
            {"source": "OpenAI", "title": "A", "url": "https://openai.com/a", "published_at": now_iso()},
            {"source": "TechCrunch AI", "title": "B", "url": "https://techcrunch.com/b", "published_at": now_iso()},
        ]
        result = agent.validate_cluster(cluster, articles)
        assert result["confidence"] > 0.6
        assert result["recommendation"] == "publish"

    def test_validate_cluster_stale_article_rejected(self, test_db):
        from agents.fact_checker_agent import FactCheckerAgent
        agent = FactCheckerAgent()
        cluster = make_cluster(1)
        articles = [{"source": "X", "title": "Old", "url": "https://x.com/y", "published_at": "2020-01-01T00:00:00+00:00"}]
        result = agent.validate_cluster(cluster, articles)
        assert result["confidence"] < 0.6
        assert any("predates" in f for f in result["flags"])

    def test_validate_cluster_no_articles(self, test_db):
        from agents.fact_checker_agent import FactCheckerAgent
        agent = FactCheckerAgent()
        result = agent.validate_cluster(make_cluster(1), [])
        assert result["confidence"] == 0.0
        assert result["recommendation"] == "reject"


# ---------------------------------------------------------------------------
# CEO Agent
# ---------------------------------------------------------------------------
class TestCEOAgent:
    def test_handle_query_uses_llm(self, test_db, monkeypatch):
        from agents.ceo_agent import CEOAgent
        agent = CEOAgent()
        monkeypatch.setattr(agent, "call_llm", lambda *a, **k: "We sent 5 digests this week.")
        answer = agent.handle_query("How many digests this week?")
        assert "5 digests" in answer

    def test_handle_query_llm_down_returns_apology(self, test_db, monkeypatch):
        from agents.ceo_agent import CEOAgent
        agent = CEOAgent()
        monkeypatch.setattr(agent, "call_llm", lambda *a, **k: None)
        answer = agent.handle_query("Status?")
        assert "unable to reach" in answer.lower()

    def test_generate_status_report_falls_back_to_template(self, test_db, monkeypatch):
        from agents.ceo_agent import CEOAgent
        agent = CEOAgent()
        monkeypatch.setattr(agent, "call_llm", lambda *a, **k: None)
        report = agent.generate_status_report()
        assert "ALEX" in report
        assert "template mode" in report

    def test_escalate_to_board_records_and_returns(self, test_db):
        from agents.ceo_agent import CEOAgent
        agent = CEOAgent()
        result = agent.escalate_to_board("CRITICAL", "All LLM providers down")
        assert result["severity"] == "CRITICAL"
        assert agent.escalations[-1] == result


# ---------------------------------------------------------------------------
# State Manager (Task 1.3 regression coverage alongside the new agents)
# ---------------------------------------------------------------------------
class TestStateManagerRegression:
    def test_mark_and_filter_round_trip(self, test_db):
        from db import get_connection
        conn = get_connection()
        conn.execute(
            "INSERT INTO clusters (id, created_at, headline, importance_score, included_in_digest) "
            "VALUES (1, ?, 'H', 5, 0)", (now_iso(),),
        )
        conn.commit()
        conn.close()

        from agents.state_manager import StateManager
        sm = StateManager()
        assert sm.mark_as_sent([1], "2026-08-08-daily") == 1
        remaining = sm.filter_unsent_clusters([{"id": 1, "sent_at": now_iso()}, {"id": 2, "sent_at": None}])
        assert [c["id"] for c in remaining] == [2]
