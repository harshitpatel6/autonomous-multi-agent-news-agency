# Troubleshooting

## Startup fails: "STARTUP FAILED: ..."
`utils/api_validator.py` rejects missing/placeholder API keys before the pipeline runs.
- Check `.env` has a real `ANTHROPIC_API_KEY` and/or `GROQ_API_KEY` (not the sample
  `sk_ant_YOUR_ACTUAL_KEY_HERE` placeholder).
- At least one provider must validate; the system runs in degraded/reduced mode
  otherwise but a *complete* absence of usable keys is a fail-fast.

## Same stories appear in consecutive digests
This should be structurally impossible (`StateManager` + sent-content filters in
`dedup.py`/`summarize.py`), so if it happens:
1. Check `clusters.sent_at` is actually being set: `ceo_cli.py metrics` → digest stats.
2. Confirm `digest.py:mark_as_sent()` ran (look for `✓ Marked N clusters as sent` in logs).
3. `agents/state_manager.py:reset_sent_status()` is TEST-ONLY — make sure nothing calls
   it in production paths.

## Digest comes back empty / "No valid content for digest"
Read the pipeline output — it tells you which stage rejected everything:
- **QA Agent FAIL**: all candidate clusters had stale/missing dates. Check
  `LOOKBACK_HOURS` / `ABSOLUTE_CUTOFF_DATE` in `config.py` aren't too strict, and that
  `ingest.py` is actually pulling fresh articles (RSS feed may be stale/dead).
- **Fact-Checker rejected everything**: low `confidence` scores usually mean
  single-source, unreputable-source, or malformed-URL articles. Check
  `agent_logs` for `FactCheckerAgent.validate_cluster` entries.
- **Editor found 0 clusters**: usually upstream of the above — nothing reached it.

## QA keeps requesting backups but none arrive
`EditorAgent.fetch_backup_stories` only pulls unsent, unused, already-summarized
clusters. If the backlog is thin (e.g. right after `archive_old_sent()` or a fresh
DB), there may genuinely be nothing left. Run `ingest.py` again to top up the pool.

## "All LLM providers failed" / digest built in degraded mode
Both Claude and Groq calls are failing (or their circuit breakers are open — see
`utils/error_handling.py:CircuitBreaker`, default: opens after 5 consecutive failures,
60s cooldown). The system will:
1. Log a CRITICAL entry and escalate to the CEO Agent (`ceo_cli.py status` will surface it).
2. Fall back to `agents/degraded_mode.py`'s rule-based clustering/scoring so a digest
   still ships, just with lower editorial quality.
Check API key validity, provider status pages, and rate limits. The breaker resets on
the next successful call after cooldown.

## CEO CLI errors or gives generic apology text
`ceo_agent.handle_query`/`generate_status_report` fall back to a template response when
`call_llm` returns `None` — that's the circuit breaker / provider outage case above, not
a CLI bug. Verify with `python3 -c "from agents.base_agent import CLAUDE_AVAILABLE, GROQ_AVAILABLE; print(CLAUDE_AVAILABLE, GROQ_AVAILABLE)"`.

## Tests fail only when run together (`pytest` at repo root, not `pytest tests/`)
Known: several legacy root-level scripts (`test_migration.py`, `test_task_1_4.py`,
`test_duplicate_prevention.py`, etc.) predate the `tests/` package, aren't proper
pytest fixtures, and mutate global module state (e.g. monkeypatch `get_connection`
without teardown) — they pass individually but pollute state for files that run after
them alphabetically. Run `pytest tests/ -q` for the actual agent/pipeline test suite;
run legacy root scripts individually if needed.

## Migration script errors on a fresh DB
`db_migrate.py` expects `digest.db` to already exist with the base schema. On a
brand-new checkout, run `python3 -c "from db import init_db; init_db()"` first (or just
`python3 main.py`, which calls `init_db()` on startup), then `db_migrate.py`.

## Email not sending despite `DIGEST_TEST_MODE=0`
- Confirm SMTP creds work standalone (e.g. `python3 -c "import smtplib; ..."` quick check).
- Gmail requires an *app password*, not your account password, if 2FA is enabled.
- Check `send_email.py` output/logs for the raw SMTP exception — it's not swallowed.

## Where to look for more detail
Every agent action is in the `agent_logs` table:
```bash
python3 -c "from utils.agent_logger import query_recent_logs; import json; print(json.dumps(query_recent_logs(limit=20), indent=2))"
python3 -c "from utils.agent_logger import query_failures; import json; print(json.dumps(query_failures(hours=48), indent=2))"
```
