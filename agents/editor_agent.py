"""
Editor Agent (Task 1.5 / 2.6): selects the best stories for the digest and,
when QA rejects stories, fetches backup replacements so the pipeline still ships.
"""
from typing import Dict, List

from config import DB_PATH, TOP_N_STORIES
from db import get_connection
from agents.base_agent import Agent
from agents.message_router import register_agent

EDITOR_SELECTION_PROMPT = """You are the Editor-in-Chief of an AI news digest. Select the top {target_count} \
most important and diverse stories from this list:

{stories_context}

Selection criteria:
1. Importance score (higher is better)
2. Diversity across categories (avoid too many similar stories)
3. Timeliness and relevance
4. Story quality

Respond with JSON array of story numbers (1-indexed):
{{"selected": [1, 3, 5, 7, 9, 11, 12, 14, 16, 18, 20, 22]}}
"""


class EditorAgent(Agent):
    def __init__(self):
        super().__init__("EditorAgent")

    def select_stories(self, clusters: List[Dict], target_count: int = TOP_N_STORIES) -> List[Dict]:
        """Choose the best `target_count` clusters, using the LLM with a deterministic fallback."""
        if len(clusters) <= target_count:
            return clusters

        stories_context = "\n".join(
            f"{i+1}. {c['headline']} (Score: {c['importance_score']}, Category: {c['category']})"
            for i, c in enumerate(clusters[: target_count * 2])
        )
        prompt = EDITOR_SELECTION_PROMPT.format(target_count=target_count, stories_context=stories_context)

        response = self.call_llm(prompt, max_tokens=500, json_mode=True)
        selection = self.parse_json(response)
        if selection and "selected" in selection:
            indices = [i - 1 for i in selection["selected"] if 0 < i <= len(clusters)]
            selected = [clusters[i] for i in indices if i < len(clusters)]
            if len(selected) >= target_count // 2:
                self.logger.log_action("select_stories", output_data={"count": len(selected)}, success=True)
                return selected[:target_count]

        # Deterministic fallback: score-sorted with per-category diversity cap
        categories_used, selected = {}, []
        for cluster in sorted(clusters, key=lambda x: x["importance_score"], reverse=True):
            category = cluster.get("category") or "Other"
            if categories_used.get(category, 0) >= 3:
                continue
            selected.append(cluster)
            categories_used[category] = categories_used.get(category, 0) + 1
            if len(selected) >= target_count:
                break
        self.logger.log_action("select_stories", output_data={"count": len(selected), "mode": "fallback"}, success=True)
        return selected

    def curate_best_of(self, clusters: List[Dict], target_count: int, min_score: int = 7) -> List[Dict]:
        """
        Task 5.3: Weekly "Best of" curation — stricter quality bar and tighter
        per-category diversity cap than the daily select_stories(), so a week's
        worth of clusters gets distilled down to genuinely the best stories.
        """
        candidates = [c for c in clusters if c.get("importance_score", 0) >= min_score]
        if not candidates:
            candidates = clusters  # nothing cleared the bar; don't ship an empty weekly digest

        categories_used, selected = {}, []
        for cluster in sorted(candidates, key=lambda x: x["importance_score"], reverse=True):
            category = cluster.get("category") or "Other"
            if categories_used.get(category, 0) >= 2:  # tighter cap than daily's 3
                continue
            selected.append(cluster)
            categories_used[category] = categories_used.get(category, 0) + 1
            if len(selected) >= target_count:
                break

        self.logger.log_action(
            "curate_best_of", input_data={"candidates": len(clusters), "min_score": min_score},
            output_data={"selected": len(selected)}, success=True,
        )
        print(f"📰 Editor Agent: curated {len(selected)} 'Best of the Week' stories from {len(clusters)} candidates")
        return selected

    def fetch_backup_stories(self, exclude_ids: List[int], needed: int) -> List[Dict]:
        """
        Fetch additional unsent, unused clusters to replace ones QA rejected.
        Marks returned clusters with backup_used=1 for observability.
        """
        if needed <= 0:
            return []

        conn = get_connection()
        placeholders = ",".join("?" * len(exclude_ids)) if exclude_ids else None
        query = """
            SELECT id, headline, category, summary, importance_score, created_at, sent_at
            FROM clusters
            WHERE summary IS NOT NULL AND included_in_digest = 0 AND sent_at IS NULL
        """
        params: List = []
        if placeholders:
            query += f" AND id NOT IN ({placeholders})"
            params.extend(exclude_ids)
        query += " ORDER BY importance_score DESC LIMIT ?"
        params.append(needed)

        rows = conn.execute(query, params).fetchall()

        backups = []
        for row in rows:
            # id + summary_raw needed by check_content_grounding()'s get_full_text lookup -
            # see the matching comment in agent_coordinator.py / publish.py. Backup clusters
            # go through the same grounding gate as primary ones (digest.py), so they need
            # the same columns.
            articles = conn.execute(
                "SELECT id, source, title, url, summary_raw, published_at, fetched_at FROM articles WHERE cluster_id = ?",
                (row["id"],),
            ).fetchall()
            cluster_dict = dict(row)
            cluster_dict["articles"] = [dict(a) for a in articles]
            backups.append(cluster_dict)

        if backups:
            conn.executemany(
                "UPDATE clusters SET backup_used = 1 WHERE id = ?",
                [(c["id"],) for c in backups],
            )
            conn.commit()
        conn.close()

        self.logger.log_action(
            "fetch_backup_stories",
            input_data={"needed": needed, "excluded": len(exclude_ids)},
            output_data={"found": len(backups)},
            success=True,
        )
        print(f"📰 Editor Agent: fetched {len(backups)}/{needed} backup stories")
        return backups

    def handle_message(self, message: Dict) -> Dict:
        """Message-router entrypoint: {type: 'select_stories'|'fetch_backup', payload: {...}}"""
        payload = message.get("payload", {})
        if message["type"] == "select_stories":
            result = self.select_stories(payload["clusters"], payload.get("target_count", TOP_N_STORIES))
            return {"stories": result}
        if message["type"] == "curate_best_of":
            result = self.curate_best_of(
                payload["clusters"], payload.get("target_count", TOP_N_STORIES),
                payload.get("min_score", 7),
            )
            return {"stories": result}
        if message["type"] == "fetch_backup":
            result = self.fetch_backup_stories(payload.get("exclude_ids", []), payload.get("needed", 0))
            return {"stories": result}
        return {"error": f"unknown message type {message['type']}"}


editor_agent = EditorAgent()
register_agent("editor", editor_agent.handle_message)
