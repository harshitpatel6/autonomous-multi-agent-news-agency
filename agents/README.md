# Agent Architecture

This directory implements the multi-agent system described in
`.kiro/specs/autonomous-ai-news-agency/`. Every agent shares one base class and
communicates through one router — that's the whole protocol.

## Base class: `base_agent.py`

`class Agent` gives every specialized agent, for free:

- `call_llm(prompt, system_prompt, max_tokens, json_mode, retries)` — tries Claude first,
  retries transient errors (timeout/429/503) with exponential backoff, falls back to Groq,
  and respects a circuit breaker per provider (`utils/error_handling.py`).
- `self.logger` — an `AgentLogger` (see `utils/agent_logger.py`) that writes every action
  to the `agent_logs` table: agent name, action, input/output, success, error, latency.
- `parse_json(text, default)` — safe JSON parsing helper for LLM responses.

Subclass it, call `super().__init__("YourAgentName")`, and you inherit all of this.

## Message protocol: `message_router.py`

Agents don't call each other's methods directly (except where a return value is needed
immediately, like the QA↔Editor backup loop in `digest.py`). Instead:

```python
from agents.message_router import router
response = router.send(sender="coordinator", recipient="fact_checker",
                        msg_type="validate_cluster", payload={...})
```

Every message is `{sender, recipient, type, payload, timestamp}` and every exchange is
logged. Agents register themselves on import via `register_agent(name, handler)` — see
the bottom of each agent module. `AGENT_REGISTRY` holds `{name: handler}`.

`router.broadcast(sender, msg_type, payload)` fans a message out to every other
registered agent (used for things like system-wide notices).

## Agents

| Name in registry | Class | File |
|---|---|---|
| `qa` | `QAAgent` | `qa_agent.py` |
| `editor` | `EditorAgent` | `editor_agent.py` |
| `fact_checker` | `FactCheckerAgent` | `fact_checker_agent.py` |
| `ceo` | `CEOAgent` | `ceo_agent.py` |
| `reporter:<beat>` | `ReporterAgent` subclasses | `reporter_agent.py` |

### QA Agent — `qa_agent.py`
`validate_clusters_for_digest(clusters, min_count)` deterministically checks each
cluster's articles (dates within `LOOKBACK_HOURS`/`ABSOLUTE_CUTOFF_DATE`, headline/summary
present) and returns `{verdict: PASS|PARTIAL|FAIL, valid_clusters, rejected, backup_request}`.
`backup_request` is `{needed, exclude_ids}` when the valid set falls short of `min_count`.

### Editor Agent — `editor_agent.py`
`select_stories(clusters, target_count)` — LLM-ranked selection with a deterministic
score+diversity fallback. `fetch_backup_stories(exclude_ids, needed)` — pulls the next-best
unsent, unused clusters from the DB (marking `backup_used=1`) when QA rejects stories.

### Fact-Checker Agent — `fact_checker_agent.py`
`validate_cluster(cluster, articles)` — pure heuristics, no LLM call: date consistency,
source reputation (`REPUTABLE_SOURCES`), multi-source corroboration, URL sanity. Returns
`{confidence: 0.0-1.0, flags, recommendation: publish|review|reject}`.

### Reporter Agents — `reporter_agent.py`
`ReporterAgent` base class + `CompanyNewsReporter` / `ResearchReporter` / `ToolsReporter` /
`GeneralReporter`. Each has a `beat_focus` prompt fragment that changes what the LLM
emphasizes. `get_reporter_for_category(category)` routes a cluster to its specialist;
`summarize.py` calls these in parallel via `ThreadPoolExecutor`.

### CEO Agent "ALEX" — `ceo_agent.py`
`generate_status_report(detailed)`, `handle_query(question)`, `handle_strategic_command(cmd)`,
`escalate_to_board(severity, summary, details)`. Falls back to a template report if both
LLMs are unreachable. Driven interactively via `ceo_cli.py` at the repo root.

### Degraded Mode — `degraded_mode.py`
Not message-routed (it's a last resort, invoked directly by the coordinator). Provides
`cluster_by_source_and_date`, `extract_simple_summary`, `score_by_date`, and
`run_degraded_pipeline` — a fully rule-based path used when both LLM circuit breakers are
open. Calls `ceo_agent.escalate_to_board("CRITICAL", ...)` on activation.

### State Manager — `state_manager.py`
Not LLM-backed. `mark_as_sent`, `filter_unsent_clusters`, `get_unsent_cluster_ids`,
`archive_old_sent`, `get_sent_stats`, `reset_sent_status` (testing only). This is what
guarantees two pipeline runs never show the same story twice.

## Extending: adding a new agent

1. Create `agents/your_agent.py`, subclass `Agent`, call `super().__init__("YourAgent")`.
2. Implement your methods using `self.call_llm(...)` for any LLM work — retries/fallback/
   circuit-breaking/logging come for free.
3. Add a `handle_message(self, message)` method that dispatches on `message["type"]`.
4. At module scope: instantiate a singleton and `register_agent("your_agent", instance.handle_message)`.
5. Import your module somewhere on the startup path (e.g. `agent_coordinator.py`) so it
   actually registers — importing for side effects is the registration mechanism.
6. Add unit tests to `tests/test_agents.py` mocking `call_llm` for deterministic runs.

## Error handling policy (Task 3.4)

Severity levels live in `utils/error_handling.py`: `INFO`, `WARNING`, `ERROR`, `CRITICAL`.
- Transient errors (timeout/429/503) → retried with backoff inside `call_llm`.
- Persistent per-provider failures → circuit breaker opens, next agent call skips that
  provider and falls through to the next one (Claude → Groq → degraded mode).
- `CRITICAL` → immediate `ceo_agent.escalate_to_board(...)` call, so a human sees it via
  `ceo_cli.py status` or `ceo_cli.py ask`.
