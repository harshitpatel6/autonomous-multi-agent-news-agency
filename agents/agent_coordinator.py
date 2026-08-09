"""
Agent Coordinator (Task 2.6 — refactored): orchestrates QA, Fact-Checker, and
Editor agents via the MessageRouter instead of inlining agent logic. Generic
LLM/retry/logging concerns now live in agents/base_agent.py; this module is pure
orchestration. Falls back to agents/degraded_mode.py when every LLM is down.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple
import sqlite3

from config import DB_PATH, LOOKBACK_HOURS, MIN_IMPORTANCE_SCORE, TOP_N_STORIES

from agents.message_router import router
# Import agents so they self-register with the router (registration is a side effect of import).
from agents import qa_agent as _qa_module        # noqa: F401
from agents import editor_agent as _editor_module  # noqa: F401
from agents import fact_checker_agent as _fc_module  # noqa: F401
from agents import ceo_agent as _ceo_module        # noqa: F401
from agents.degraded_mode import run_degraded_pipeline, activate as activate_degraded_mode
from agents.base_agent import CLAUDE_AVAILABLE, GROQ_AVAILABLE
from utils import mode_state


class AgentCoordinator:
    """Thin orchestration layer: wires agent inputs/outputs together via the router."""

    def __init__(self):
        if not CLAUDE_AVAILABLE and not GROQ_AVAILABLE:
            print("⚠️  No LLM clients available — coordinator will rely on degraded mode.")
        self.router = router

    def get_clusters_with_articles(self) -> List[Dict]:
        """
        Unsent clusters above the importance bar, with their articles attached.
        Lookback window and quality bar flex with the digest mode (Task 5.3):
        daily uses config defaults, weekly widens the window to 7 days and raises
        the importance bar for "Best of" curation.
        """
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        lookback_hours = mode_state.get_lookback_hours()
        min_score = mode_state.get_min_importance_score()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()

        clusters = conn.execute("""
            SELECT id, headline, category, summary, importance_score, created_at, sent_at
            FROM clusters
            WHERE summary IS NOT NULL
                  AND included_in_digest = 0
                  AND sent_at IS NULL
                  AND importance_score >= ?
                  AND created_at >= ?
            ORDER BY importance_score DESC
        """, (min_score, cutoff)).fetchall()

        result = []
        for cluster in clusters:
            articles = conn.execute(
                "SELECT source, title, url, published_at, fetched_at FROM articles WHERE cluster_id = ?",
                (cluster["id"],),
            ).fetchall()
            cluster_dict = dict(cluster)
            cluster_dict["articles"] = [dict(a) for a in articles]
            result.append(cluster_dict)

        conn.close()
        return result

    def run_full_validation_pipeline(self) -> Tuple[bool, List[Dict], str]:
        """
        Full pipeline, routed through the MessageRouter:
        load clusters -> Fact-Checker scores each -> Editor selects top N -> return.
        QA's PASS/PARTIAL/FAIL + backup loop runs downstream in digest.py (Task 1.5),
        since that stage needs write access to the digest-building context.
        """
        print("\n" + "=" * 70)
        print("🚀 MULTI-AGENT VALIDATION PIPELINE (via MessageRouter)")
        print("=" * 70)

        clusters = self.get_clusters_with_articles()
        print(f"\n📦 Loaded {len(clusters)} candidate clusters")

        if not clusters:
            return False, [], "No clusters available for digest"

        if not CLAUDE_AVAILABLE and not GROQ_AVAILABLE:
            activate_degraded_mode("No LLM providers configured at coordinator startup")
            all_articles = [a for c in clusters for a in c["articles"]]
            fallback_clusters = run_degraded_pipeline(all_articles, TOP_N_STORIES)
            return True, fallback_clusters, "✅ Degraded mode: rule-based digest generated (no LLM available)"

        # Fact-Checker validates each cluster (routed message, not a direct call)
        valid_clusters = []
        for cluster in clusters:
            response = self.router.send(
                "coordinator", "fact_checker", "validate_cluster",
                {"cluster": cluster, "articles": cluster["articles"]},
            )
            if response and response.get("recommendation") in ("publish", "review"):
                cluster["fact_check_score"] = response["confidence"]
                valid_clusters.append(cluster)

        print(f"✓ Fact-Checker Agent: {len(valid_clusters)}/{len(clusters)} clusters passed")

        if not valid_clusters:
            return False, [], "All clusters failed fact-check validation"

        # Editor selects the best stories (routed message). Weekly mode gets the
        # stricter "Best of" curation instead of the daily selection (Task 5.3).
        mode = mode_state.get_mode()
        if mode == mode_state.WEEKLY:
            editor_response = self.router.send(
                "coordinator", "editor", "curate_best_of",
                {"clusters": valid_clusters, "target_count": TOP_N_STORIES, "min_score": 7},
            )
        else:
            editor_response = self.router.send(
                "coordinator", "editor", "select_stories",
                {"clusters": valid_clusters, "target_count": TOP_N_STORIES},
            )
        selected_clusters = editor_response["stories"] if editor_response else valid_clusters[:TOP_N_STORIES]

        print(f"✓ Editor Agent: Selected {len(selected_clusters)} stories for publication")

        report = f"""
MULTI-AGENT VALIDATION COMPLETE
{'='*70}
Initial clusters: {len(clusters)}
After Fact-Checker: {len(valid_clusters)} clusters
After Editor selection: {len(selected_clusters)} stories

✅ READY FOR QA / PUBLICATION
"""
        return True, selected_clusters, report


# Singleton instance
coordinator = AgentCoordinator()
