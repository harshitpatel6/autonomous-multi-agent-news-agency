# Tasks: Autonomous AI News Agency

**Spec Type:** feature  
**Status:** draft  
**Related:** requirements.md, design.md

---

## Overview

Transform the newsletter system into a fully autonomous AI news agency with specialized agents. Implementation focuses on critical fixes first, then multi-agent architecture, observability, testing, and future enhancements.

---

## Tasks

- [x] 1.1 API Key Validation & Health Checks - Add startup validation for Anthropic and Groq API keys. Detect invalid/placeholder keys and provide clear error messages. Create utils/api_validator.py, implement validation functions, call validators in main.py on startup. System must detect placeholder keys, make test API calls, print clear errors, and proceed with available keys or fail fast.

- [x] 1.2 Database Schema Migration - Add new columns to clusters table and create new tables for state management and observability. Add columns (sent_at, digest_id, quality_score, backup_used, validation_status, fact_check_score), create digests and agent_logs tables, create migration script db_migrate.py, update db.py. Migration must be idempotent and preserve existing data.

- [x] 1.3 State Manager - Sent Content Tracking [depends on: 1.2] - Implement StateManager class to track sent clusters and prevent duplicates across runs. Create agents/state_manager.py with mark_as_sent(), filter_unsent_clusters(), archive_old_sent(), and get_sent_stats() methods. Integrate into digest.py. Running pipeline twice must show different stories.

- [x] 1.4 Enhanced Cleanup - Filter Sent Content [depends on: 1.2, 1.3] - Update cleanup and dedup stages to filter out already-sent clusters and articles. Modify dedup.py and summarize.py to exclude sent content, add logging for filtered content. Clustering must never include articles from sent clusters.

- [x] 1.5 QA Agent - Backup Story Mechanism - Implement QA Agent's ability to request backup stories from Editor Agent when validation fails. Refactor agents/qa_agent.py to return PASS/PARTIAL/FAIL verdict with backup_request. Create agents/editor_agent.py with select_stories() and fetch_backup_stories(). Integrate QA ↔ Editor communication in digest.py. Pipeline must succeed with valid + backup stories.

- [x] 2.1 Agent Message Protocol & Router - Implement message-passing protocol for agent communication. Create agents/message_router.py with MessageRouter class, send() and broadcast() methods. Define message format (JSON schema), create AGENT_REGISTRY, add message logging to agent_logs table. Messages must follow standardized format and route correctly.

- [x] 2.2 CEO Agent "ALEX" [depends on: 2.1] - Implement CEO Agent for board communication and strategic oversight. Create agents/ceo_agent.py with CEOAgent class (handle_query, generate_status_report, handle_strategic_command, escalate_to_board methods). Define CEO system prompt, implement Claude → Groq fallback, add template responses. CEO must respond with executive summaries and handle strategic commands.

- [x] 2.3 CEO CLI Interface [depends on: 2.2] - Create command-line interface for board member to interact with CEO Agent. Create ceo_cli.py script with commands (status, status --detailed, ask, command). Add argument parsing, format output for readability, error handling. CLI must provide intuitive interface with clear output and help text.

- [x] 2.4 Reporter Agents (Beat-Based) [depends on: 2.1] - Implement specialized Reporter Agents for different beats. Create agents/reporter_agent.py with ReporterAgent base class and beat-specific instances (CompanyNewsReporter, ResearchReporter, ToolsReporter). Implement summarize_cluster() with beat-specific prompts. Integrate into summarize.py with parallel processing. Each reporter must specialize in their beat.

- [x] 2.5 Enhanced Fact-Checker Agent [depends on: 2.1] - Enhance Fact-Checker Agent with better validation logic. Create/refactor agents/fact_checker_agent.py with heuristic-based checks (date consistency, source reputation, multiple source corroboration). Implement validate_cluster() returning confidence score (0.0-1.0). Flag inconsistencies and provide recommendations.

- [x] 2.6 Refactor Agent Coordinator [depends on: 2.1, 2.2, 2.4, 2.5] - Refactor existing agent_coordinator.py to use new agent architecture and message router. Move generic LLM logic to base Agent class, update run_full_validation_pipeline() to use message router, integrate all agents, remove deprecated code, update imports. All agents must communicate via message router with clean separation of concerns.

- [x] 3.1 Structured Logging System [depends on: 1.2] - Implement structured logging for all agent actions. Create utils/agent_logger.py with AgentLogger class and log_action() method. Integrate into all agent classes, add log levels (DEBUG, INFO, WARNING, ERROR), create query functions. All agent actions must be logged to database with input, output, success/failure, and execution time.

- [x] 3.2 Metrics Collection System [depends on: 3.1] - Implement metrics collection for agent performance and system health. Create utils/metrics_collector.py with MetricsCollector class and methods (get_agent_performance, get_api_health, get_digest_stats, get_quality_metrics). Integrate into CEO Agent status reports, add CLI command. Metrics must show success rates, latencies, and quality scores.

- [x] 3.3 Degraded Mode Implementation - Implement fallback to rule-based heuristics when all LLMs fail. Create agents/degraded_mode.py with fallback functions (cluster_by_source_and_date, extract_simple_summary, score_by_date). Add degraded mode flag in config, integrate into agent_coordinator, log activation, notify CEO. System must generate digest even when all LLM APIs fail.

- [x] 3.4 Error Handling & Recovery [depends on: 2.2] - Enhance error handling with graceful recovery and CEO escalation. Define error severity levels (INFO, WARNING, ERROR, CRITICAL), implement retry logic with exponential backoff, add circuit breaker for failing APIs. CEO Agent must handle escalations. Transient errors must trigger retries, persistent errors trigger fallbacks, critical errors escalate to CEO.

- [x] 4.1 Unit Tests for All Agents [depends on: 2.1, 2.2, 2.4, 2.5, 2.6] - Comprehensive unit tests for each agent. Create tests/test_agents.py with tests for QA Agent, Editor Agent, Reporter Agent, Fact-Checker, CEO Agent, and State Manager. Mock LLM API calls, test success and failure paths, achieve >80% code coverage. All agent methods must be unit tested with edge cases covered.

- [x] 4.2 Integration Tests [depends on: 4.1] - End-to-end integration tests for full pipeline. Create tests/test_pipeline.py with tests for full pipeline, QA failure → backup stories, duplicate prevention, API failures → degraded mode, and state management. Use test database, mock external services (RSS feeds, SMTP), validate final digest content. Critical user stories must be validated.

- [x] 4.3 Documentation Updates - Update all documentation to reflect new multi-agent architecture. Update README.md (architecture diagram, agent descriptions, setup, CEO CLI), update agents/README.md (responsibilities, communication protocol, extension guide), create DEPLOYMENT.md (deployment guide, environment variables, migration steps), create TROUBLESHOOTING.md (common issues, recovery procedures). Documentation must be comprehensive and enable new users to set up the system.

- [x] 5.1 Scout Agent - Source Discovery [depends on: 4.2] [optional] - Implement Scout Agent to discover new RSS sources autonomously. Create agents/scout_agent.py with source discovery logic using web search, validate feed URLs and quality, implement add_source() and remove_dead_source() methods, schedule weekly runs, report to CEO Agent. Scout must discover new feeds, validate quality, and remove dead feeds.

- [x] 5.2 LangGraph Orchestration [depends on: 4.2] [optional] - Integrate LangGraph for complex multi-agent workflows. Install langgraph package, define workflow graph for digest generation, convert linear pipeline to graph-based workflow, add conditional edges, implement parallel agent execution, add workflow visualization. Pipeline must use LangGraph for orchestration with improved performance.

- [x] 5.3 Weekly Digest Mode [depends on: 4.2] [optional] - Add weekly digest mode with "Best of" curation. Add DIGEST_MODE config, adjust LOOKBACK_HOURS based on mode, Editor Agent applies "Best of" curation for weekly, different email template, CEO Agent can switch modes. Weekly mode must aggregate 7 days with higher quality bar.

- [x] 5.4 Next.js Web Dashboard [depends on: 4.2] [optional] - Build web dashboard for CEO Agent interaction and metrics visualization. Create Next.js project, build API endpoints (FastAPI backend), implement pages (dashboard home, agent performance, recent digests, CEO chat, configuration), add real-time updates (WebSocket), deploy to Vercel/Netlify. Web UI must provide CEO chat and real-time metrics with responsive design.

---

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": ["1.1", "1.2", "1.5", "2.1"],
      "description": "Initial setup - API validation, DB migration, QA backup mechanism, message router"
    },
    {
      "wave": 2,
      "tasks": ["1.3", "2.2", "2.4", "2.5"],
      "dependencies": ["1.2", "2.1"],
      "description": "State manager, CEO Agent, Reporter Agents, Fact-Checker"
    },
    {
      "wave": 3,
      "tasks": ["1.4", "2.3"],
      "dependencies": ["1.3", "2.2"],
      "description": "Cleanup filter, CEO CLI"
    },
    {
      "wave": 4,
      "tasks": ["2.6", "3.1", "3.3"],
      "dependencies": ["2.1", "2.2", "2.4", "2.5"],
      "description": "Refactor coordinator, structured logging, degraded mode"
    },
    {
      "wave": 5,
      "tasks": ["3.2", "3.4"],
      "dependencies": ["3.1", "2.2"],
      "description": "Metrics collection, error handling & recovery"
    },
    {
      "wave": 6,
      "tasks": ["4.1"],
      "dependencies": ["2.1", "2.2", "2.4", "2.5", "2.6"],
      "description": "Unit tests for all agents"
    },
    {
      "wave": 7,
      "tasks": ["4.2", "4.3"],
      "dependencies": ["4.1"],
      "description": "Integration tests and documentation"
    },
    {
      "wave": 8,
      "tasks": ["5.1", "5.2", "5.3", "5.4"],
      "dependencies": ["4.2"],
      "description": "Future enhancements (optional, post-MVP)"
    }
  ]
}
```

---

# Implementation Plan:

## Phase 1: Critical Fixes (Week 1)
**Tasks:** 1.1, 1.2, 1.3, 1.4, 1.5

Fix immediate issues preventing reliable operation: API validation, database schema, state management, cleanup filters, and QA backup mechanism.

**Deliverables:** Zero duplicates across pipeline runs, proper API key validation, sent content tracking

---

## Phase 2: Multi-Agent Architecture (Week 2)
**Tasks:** 2.1, 2.2, 2.3, 2.4, 2.5, 2.6

Build autonomous agent system with CEO oversight: message router, CEO Agent with CLI, beat-based reporters, fact-checker, and refactored coordinator.

**Deliverables:** Fully autonomous multi-agent system with board-level communication interface

---

## Phase 3: Observability & Polish (Week 3, Part 1)
**Tasks:** 3.1, 3.2, 3.3, 3.4

Add monitoring, logging, and graceful degradation: structured logging, metrics collection, degraded mode fallbacks, enhanced error handling.

**Deliverables:** Production-ready observability and resilience

---

## Phase 4: Testing & Documentation (Week 3, Part 2)
**Tasks:** 4.1, 4.2, 4.3

Ensure production readiness: unit tests (>80% coverage), end-to-end integration tests, updated documentation.

**Deliverables:** Comprehensive test coverage and complete documentation

---

## Phase 5: Future Enhancements (Post-MVP)
**Tasks:** 5.1, 5.2, 5.3, 5.4

Advanced features based on user feedback: Scout Agent, LangGraph orchestration, weekly digest mode, web dashboard.

**Deliverables:** Enhanced autonomous capabilities and improved user experience

---

## Notes

### Critical Path
- Task 1.2 (DB Migration) is a prerequisite for many tasks - complete first
- Task 2.1 (Message Router) enables all Phase 2 agent tasks
- Backup database before Task 1.2 migration

### Development Strategy
- Wave-based parallel execution: tasks in same wave can run concurrently
- Use test database for all testing to avoid corrupting production data
- Mock LLM API calls in tests to avoid rate limits

### LLM Fallback Chain
Claude (primary) → Groq (secondary) → Heuristics (tertiary)

### Post-MVP Tasks
Tasks 5.1-5.4 are optional enhancements marked with Optional: true. Can be skipped or implemented based on priorities.
