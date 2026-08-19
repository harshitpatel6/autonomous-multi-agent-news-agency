"""
LangGraph Orchestration (Task 5.2): graph-based version of the digest pipeline,
replacing the linear coordinator call chain with explicit nodes + conditional
edges for the QA <-> Editor backup loop, and parallel fan-out for fact-checking.

This is an alternative entrypoint to agents.agent_coordinator.run_full_validation_pipeline
— opt in via config.USE_LANGGRAPH_ORCHESTRATION. Both paths produce the same
(success, selected_clusters, report) shape.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

from config import TOP_N_STORIES
from agents.message_router import router
from agents.agent_coordinator import AgentCoordinator
from agents.degraded_mode import run_degraded_pipeline, activate as activate_degraded_mode
from agents.base_agent import CLAUDE_AVAILABLE, GROQ_AVAILABLE, GEMINI_AVAILABLE
from utils import mode_state

# Import so the agents self-register on the router
from agents import qa_agent as _qa_module        # noqa: F401
from agents import editor_agent as _editor_module  # noqa: F401
from agents import fact_checker_agent as _fc_module  # noqa: F401

MAX_BACKUP_ROUNDS = 3


class PipelineState(TypedDict, total=False):
    clusters: List[Dict]
    valid_clusters: List[Dict]
    selected_clusters: List[Dict]
    qa_result: Dict
    backup_rounds: int
    final_clusters: List[Dict]
    success: bool
    report: str


_coordinator = AgentCoordinator()


def load_clusters_node(state: PipelineState) -> PipelineState:
    clusters = _coordinator.get_clusters_with_articles()
    return {"clusters": clusters}


def fact_check_node(state: PipelineState) -> PipelineState:
    """Parallel agent execution (Task 5.2): fan out fact-check calls across a thread pool."""
    clusters = state["clusters"]
    if not clusters:
        return {"valid_clusters": []}

    def check(cluster):
        response = router.send("graph", "fact_checker", "validate_cluster",
                                {"cluster": cluster, "articles": cluster["articles"]})
        return cluster, response

    valid = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for cluster, response in pool.map(check, clusters):
            if response and response.get("recommendation") in ("publish", "review"):
                cluster["fact_check_score"] = response["confidence"]
                valid.append(cluster)

    print(f"✓ [graph] Fact-Checker: {len(valid)}/{len(clusters)} clusters passed (parallel)")
    return {"valid_clusters": valid}


def editor_select_node(state: PipelineState) -> PipelineState:
    valid_clusters = state.get("valid_clusters", [])
    if not valid_clusters:
        return {"selected_clusters": []}

    mode = mode_state.get_mode()
    if mode == mode_state.WEEKLY:
        response = router.send("graph", "editor", "curate_best_of",
                                {"clusters": valid_clusters, "target_count": TOP_N_STORIES, "min_score": 7})
    else:
        response = router.send("graph", "editor", "select_stories",
                                {"clusters": valid_clusters, "target_count": TOP_N_STORIES})
    selected = response["stories"] if response else valid_clusters[:TOP_N_STORIES]
    print(f"✓ [graph] Editor: selected {len(selected)} stories")
    return {"selected_clusters": selected}


def qa_validate_node(state: PipelineState) -> PipelineState:
    selected = state.get("selected_clusters", [])
    response = router.send("graph", "qa", "validate_clusters",
                            {"clusters": selected, "min_count": TOP_N_STORIES})
    result = response or {"verdict": "FAIL", "valid_clusters": [], "backup_request": None}
    print(f"✓ [graph] QA verdict: {result['verdict']}")
    return {"qa_result": result, "selected_clusters": result["valid_clusters"]}


def fetch_backup_node(state: PipelineState) -> PipelineState:
    backup_request = state["qa_result"]["backup_request"]
    response = router.send("graph", "editor", "fetch_backup",
                            {"exclude_ids": backup_request["exclude_ids"], "needed": backup_request["needed"]})
    backups = response["stories"] if response else []
    merged = state.get("selected_clusters", []) + backups
    print(f"✓ [graph] Editor fetched {len(backups)} backup stories")
    return {"selected_clusters": merged, "backup_rounds": state.get("backup_rounds", 0) + 1}


def finalize_node(state: PipelineState) -> PipelineState:
    final = state.get("selected_clusters", [])
    success = len(final) > 0
    report = (f"LangGraph pipeline complete: {len(final)} stories ready"
              if success else "LangGraph pipeline complete: no valid stories")
    return {"final_clusters": final, "success": success, "report": report}


def route_after_qa(state: PipelineState) -> str:
    """Conditional edge: loop to backup fetch on PARTIAL (up to MAX_BACKUP_ROUNDS), else finalize."""
    qa_result = state["qa_result"]
    backup_request = qa_result.get("backup_request")
    rounds = state.get("backup_rounds", 0)

    if qa_result["verdict"] == "PARTIAL" and backup_request and backup_request["needed"] > 0 and rounds < MAX_BACKUP_ROUNDS:
        return "backup"
    return "finalize"


def build_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("load_clusters", load_clusters_node)
    graph.add_node("fact_check", fact_check_node)
    graph.add_node("editor_select", editor_select_node)
    graph.add_node("qa_validate", qa_validate_node)
    graph.add_node("fetch_backup", fetch_backup_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("load_clusters")
    graph.add_edge("load_clusters", "fact_check")
    graph.add_edge("fact_check", "editor_select")
    graph.add_edge("editor_select", "qa_validate")
    graph.add_conditional_edges("qa_validate", route_after_qa, {"backup": "fetch_backup", "finalize": "finalize"})
    graph.add_edge("fetch_backup", "qa_validate")  # loop back for re-validation
    graph.add_edge("finalize", END)

    return graph.compile()


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def visualize_graph(path: str = "docs/orchestration_graph.mmd") -> str:
    """Task 5.2: workflow visualization. Writes Mermaid source and returns it."""
    mermaid = get_compiled_graph().get_graph().draw_mermaid()
    try:
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(mermaid)
    except Exception as e:
        print(f"⚠️  Could not write graph visualization to {path}: {e}")
    return mermaid


def run_langgraph_pipeline() -> "tuple[bool, List[Dict], str]":
    """Drop-in replacement for AgentCoordinator.run_full_validation_pipeline(), graph-based."""
    print("\n" + "=" * 70)
    print("🚀 MULTI-AGENT VALIDATION PIPELINE (via LangGraph)")
    print("=" * 70)

    if not CLAUDE_AVAILABLE and not GROQ_AVAILABLE and not GEMINI_AVAILABLE:
        activate_degraded_mode("No LLM providers configured at graph startup")
        clusters = _coordinator.get_clusters_with_articles()
        all_articles = [a for c in clusters for a in c["articles"]]
        fallback = run_degraded_pipeline(all_articles, TOP_N_STORIES)
        return True, fallback, "✅ Degraded mode: rule-based digest generated (no LLM available)"

    initial_state: PipelineState = {"backup_rounds": 0}
    final_state = get_compiled_graph().invoke(initial_state)

    if not final_state.get("clusters"):
        return False, [], "No clusters available for digest"

    return final_state["success"], final_state["final_clusters"], final_state["report"]


if __name__ == "__main__":
    print(visualize_graph())
