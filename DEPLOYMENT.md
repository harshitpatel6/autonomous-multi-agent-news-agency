# Deployment Guide

## 1. Prerequisites

- Python 3.10+
- An Anthropic API key (primary LLM) and, recommended, a Groq API key (fallback)
- SMTP credentials for sending the digest (Gmail app password works for testing)

## 2. Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pytest   # dev-only, for tests/
```

## 3. Environment variables (`.env`)

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (or Groq) | From console.anthropic.com. Must not be a placeholder like `sk_ant_YOUR_ACTUAL_KEY_HERE` — `utils/api_validator.py` rejects those on startup. |
| `GROQ_API_KEY` | Recommended | Fallback LLM used automatically when Claude fails/rate-limits. |
| `LLM_PROVIDER` | Yes | `claude` or `groq` — primary provider for `summarize.py`'s legacy path. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` | Yes (to send) | Standard SMTP. Port 587 (STARTTLS) is the default. |
| `FROM_EMAIL` | No | Defaults to `SMTP_USER`. |
| `DIGEST_RECIPIENT` | Yes | Where the digest is sent. |
| `DIGEST_TEST_MODE` | No | `1` (default) saves the digest to an HTML file instead of emailing; `0` sends for real. |

Never commit `.env`. `config.py` loads it via `python-dotenv`.

## 4. Database setup / migration

The schema (`db.py:SCHEMA`) is additive and idempotent — safe to run repeatedly and
safe against an existing `digest.db` with older data.

```bash
python3 db_migrate.py
```

This adds (if missing): `clusters.sent_at`, `digest_id`, `quality_score`, `backup_used`,
`validation_status`, `fact_check_score`; and creates `digests` and `agent_logs` tables.
`db_migrate.py` backs up `digest.db` before altering anything — look for
`digest.db.backup_<timestamp>` in the repo root after running it.

## 5. First run (dry run)

Leave `DIGEST_TEST_MODE=1` for your first run — it writes `digest_test_*.html` instead
of emailing, so you can inspect output safely:

```bash
python3 main.py
```

Startup validates your API keys first (`utils/api_validator.py`); it fails fast with a
clear message if both Claude and Groq are unusable.

## 6. Going live

1. Set `DIGEST_TEST_MODE=0` in `.env`.
2. Send yourself one test digest and check formatting/links.
3. Schedule it (cron shown below, or GitHub Actions / a cloud scheduler).

```cron
# Twice daily, 7am and 5pm
0 7,17 * * * cd /path/to/NEWletter && /usr/bin/python3 main.py >> run.log 2>&1
```

## 7. Operating it

```bash
python3 ceo_cli.py status              # is it healthy?
python3 ceo_cli.py status --detailed   # per-agent breakdown
python3 ceo_cli.py metrics             # raw success rates / latencies / quality
```

## 8. Rollback

Every migration run leaves a timestamped backup (`digest.db.backup_YYYYMMDD_HHMMSS`).
To roll back: stop the scheduler, `cp digest.db.backup_<ts> digest.db`, restart.

## 8b. Optional: Web Dashboard (Task 5.4)

A FastAPI backend (`api/`) + Next.js frontend (`web/`) give the CEO Agent a browser UI
alongside `ceo_cli.py`. See [web/README.md](web/README.md) for run/deploy steps.
Quick start:
```bash
pip install -r api/requirements.txt
uvicorn api.main:app --reload --port 8000   # backend
cd web && npm install && npm run dev        # frontend, in a second terminal
```

## 8c. Optional: LangGraph orchestration (Task 5.2)

Set `USE_LANGGRAPH_ORCHESTRATION=1` in `.env` to route the digest pipeline through
`agents/orchestration_graph.py` (StateGraph with conditional QA↔Editor backup edges and
parallel fact-checking) instead of the default linear coordinator. Both produce
identical output; this is opt-in since it's the newer path. Regenerate the workflow
diagram with `python3 -m agents.orchestration_graph` (writes `docs/orchestration_graph.mmd`).

## 8d. Optional: Scout Agent (Task 5.1)

`python3 -m agents.scout_agent` runs one discovery cycle (audits existing scout-added
sources, discovers new candidates via LLM, validates each with `feedparser`, and reports
to the CEO Agent). Schedule it weekly:
```cron
0 6 * * 1 cd /path/to/NEWletter && /usr/bin/python3 -m agents.scout_agent >> scout.log 2>&1
```

## 9. Tests before deploying a change

```bash
python3 -m pytest tests/ -q
```

(Note: some legacy root-level scripts like `test_migration.py`, `test_task_1_4.py` are
standalone smoke scripts, not part of the `tests/` package, and mutate global state —
run them individually, not mixed into a single `pytest` invocation with `tests/`.)
