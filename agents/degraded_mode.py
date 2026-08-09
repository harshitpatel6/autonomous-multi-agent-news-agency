"""
Degraded Mode (Task 3.3): rule-based fallbacks used when all LLM providers fail,
so the agency still ships a digest instead of going dark.
"""
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Dict, List

from config import DB_PATH, CLUSTER_SIMILARITY_THRESHOLD
from utils.agent_logger import AgentLogger

_logger = AgentLogger("DegradedMode")
_active = False


def is_active() -> bool:
    return _active


def activate(reason: str):
    """Flip the degraded-mode flag on and notify the CEO Agent."""
    global _active
    _active = True
    _logger.log_action("activate", input_data={"reason": reason}, success=True, level="ERROR")
    print(f"🛑 DEGRADED MODE ACTIVATED: {reason}")
    try:
        from agents.ceo_agent import ceo_agent
        ceo_agent.escalate_to_board("CRITICAL", f"Degraded mode activated: {reason}")
    except Exception:
        pass


def deactivate():
    global _active
    if _active:
        _logger.log_action("deactivate", success=True)
        print("✅ Degraded mode deactivated — LLM providers recovered.")
    _active = False


def cluster_by_source_and_date(articles: List[Dict]) -> List[List[Dict]]:
    """
    Rule-based clustering fallback: group by fuzzy title similarity within the same day,
    replacing the embedding/LLM-based dedup logic.
    """
    clusters: List[List[Dict]] = []
    for article in sorted(articles, key=lambda a: a.get("published_at") or ""):
        placed = False
        title = (article.get("title") or "").lower()
        day = (article.get("published_at") or "")[:10]
        for cluster in clusters:
            rep = cluster[0]
            rep_day = (rep.get("published_at") or "")[:10]
            if rep_day != day:
                continue
            similarity = SequenceMatcher(None, title, (rep.get("title") or "").lower()).ratio()
            if similarity >= CLUSTER_SIMILARITY_THRESHOLD:
                cluster.append(article)
                placed = True
                break
        if not placed:
            clusters.append([article])
    _logger.log_action("cluster_by_source_and_date", input_data={"n_articles": len(articles)},
                        output_data={"n_clusters": len(clusters)}, success=True)
    return clusters


def extract_simple_summary(articles: List[Dict]) -> Dict:
    """Deterministic summary: use the longest title as headline, truncate first snippet as summary."""
    if not articles:
        return {"headline": "Untitled", "category": "Other", "summary": "", "importance_score": 3}
    headline_source = max(articles, key=lambda a: len(a.get("title") or ""))
    snippet = (articles[0].get("summary_raw") or articles[0].get("title") or "")[:280]
    return {
        "headline": headline_source.get("title", "Untitled")[:100],
        "category": "Other",
        "summary": snippet,
        "importance_score": score_by_date(articles),
    }


def score_by_date(articles: List[Dict]) -> int:
    """Heuristic importance score: more corroborating sources + recency = higher score."""
    if not articles:
        return 1
    n_sources = len({a.get("source") for a in articles})
    now = datetime.now(timezone.utc)
    freshest_hours = None
    for a in articles:
        pub = a.get("published_at")
        if not pub:
            continue
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            hours_ago = (now - dt).total_seconds() / 3600
            freshest_hours = hours_ago if freshest_hours is None else min(freshest_hours, hours_ago)
        except Exception:
            continue

    score = 3 + min(4, n_sources)  # base 3, +1 per corroborating source up to +4
    if freshest_hours is not None and freshest_hours < 12:
        score += 2
    return max(1, min(10, score))


def run_degraded_pipeline(articles: List[Dict], target_count: int) -> List[Dict]:
    """
    End-to-end fallback pipeline: cluster -> summarize -> score -> rank, entirely
    without any LLM call. Returns cluster-shaped dicts ready for the digest builder.
    """
    raw_clusters = cluster_by_source_and_date(articles)
    result = []
    for group in raw_clusters:
        summary = extract_simple_summary(group)
        result.append({**summary, "articles": group, "created_at": datetime.now(timezone.utc).isoformat()})
    result.sort(key=lambda c: c["importance_score"], reverse=True)
    _logger.log_action("run_degraded_pipeline", output_data={"clusters": len(result)}, success=True)
    return result[:target_count]
