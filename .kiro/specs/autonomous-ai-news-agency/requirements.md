# Requirements: Autonomous AI News Agency

**Spec Type:** feature  
**Status:** draft  
**Created:** 2024-01-08  
**Owner:** Board Member (Harshit)

---

## Executive Vision

Transform the current newsletter system into a **fully autonomous AI company** where every role—from CEO to reporter to fact-checker—is handled by specialized AI agents. The board member (user) should only provide strategic oversight, never operational involvement.

**Core Principle:** Zero human intervention in day-to-day operations. The system must handle failures gracefully, make editorial decisions autonomously, and continuously improve itself.

---

## Business Goals

### BG-1: Autonomous Operations
**Priority:** P0  
**Description:** System must run completely autonomously without human intervention for operational decisions.

**Success Criteria:**
- User can run the pipeline once and forget about it
- Agents handle all failures and edge cases autonomously
- No manual debugging or intervention required for 99% of scenarios
- System self-heals when APIs fail or data is problematic

### BG-2: Board-Level Communication
**Priority:** P0  
**Description:** User interacts only with CEO Agent "ALEX" for strategic oversight and reports.

**Success Criteria:**
- User can ask ALEX for status reports, metrics, strategic decisions
- ALEX provides executive summaries without technical details
- ALEX can execute board-level commands ("change strategy", "add new focus area")
- All operational details handled by department heads, not exposed to board

### BG-3: Quality Over Quantity
**Priority:** P0  
**Description:** Only fresh, high-quality, validated stories make it to the newsletter.

**Success Criteria:**
- Zero old articles (before ABSOLUTE_CUTOFF_DATE) in any digest
- All stories validated by multiple agents (QA, Fact-Checker, Editor)
- If stories fail validation, system fetches backup stories autonomously
- Duplicate prevention across multiple pipeline runs

### BG-4: Continuous Improvement
**Priority:** P1  
**Description:** System learns and improves autonomously over time.

**Success Criteria:**
- Scout Agent discovers new RSS sources automatically
- Agents learn from failures and adjust strategies
- Performance metrics tracked and optimized automatically
- Dead/low-quality sources removed autonomously

---

## User Stories

### US-1: Board Member Strategic Oversight
**As a** board member  
**I want to** interact only with CEO Agent ALEX for strategic decisions  
**So that** I can focus on vision without operational details

**Acceptance Criteria:**
- Can ask ALEX: "What's today's digest performance?"
- Can command ALEX: "Focus more on research papers, less on company news"
- ALEX responds with executive summaries, not technical logs
- ALEX handles all delegation to department heads

**Edge Cases:**
- If ALEX API fails, system continues operation and reports failure later
- ALEX maintains conversation context across multiple queries

---

### US-2: Zero Duplicate Content Across Runs
**As a** board member  
**I want to** see different news each time I run the pipeline  
**So that** I never receive duplicate or stale content

**Acceptance Criteria:**
- Running pipeline 2-3 times shows different stories each time
- Stories marked as "sent" are never included again
- Database tracks all sent clusters and articles
- Old articles (before ABSOLUTE_CUTOFF_DATE) never appear, even on re-runs

**Current Bug:**
- User reports seeing June 2024 articles on second run
- System not properly tracking sent content

---

### US-3: Resilient QA Validation with Fallbacks
**As a** QA Agent  
**I want to** validate all stories and fetch backups if stories fail  
**So that** the newsletter always has high-quality content

**Acceptance Criteria:**
- QA Agent validates all stories against date filters, quality standards
- If stories fail validation, QA requests backup stories from Editor Agent
- Editor Agent pulls next-best stories from the queue
- Pipeline never fails completely—always produces a digest if ANY valid content exists
- Critical failures are logged but don't stop the pipeline

**Current Bug:**
- QA Agent failure (401 API error) stops entire pipeline
- No fallback mechanism to fetch alternative stories

---

### US-4: Autonomous Source Discovery
**As a** Scout Agent  
**I want to** discover new RSS sources automatically  
**So that** the system continuously expands its coverage without human input

**Acceptance Criteria:**
- Scout Agent runs weekly, searches for new AI news RSS feeds
- Validates feed quality (articles recency, reliability, content quality)
- Adds high-quality feeds to config automatically
- Removes dead/low-quality feeds after 3 consecutive failures

**Not in MVP:** This is P1 priority—can be added after core system is stable

---

### US-5: Multi-Department Agent Coordination
**As the** system  
**I want to** coordinate multiple specialized agents across departments  
**So that** each agent handles its domain expertise autonomously

**Acceptance Criteria:**
- **Editorial Department:**
  - Editor-in-Chief Agent: Final story selection, headline approval
  - Reporter Agents (3+): Specialized beats (Company News, Research, Tools)
  
- **Quality Department:**
  - QA Agent: Date validation, quality checks, backup story fetching
  - Fact-Checker Agent: Cross-reference validation, confidence scoring
  
- **Tech Department:**
  - CTO Agent: Decides tech stack, optimization strategies
  - Engineer Agents: (future) Code improvements, database optimization
  
- **Intelligence Department:**
  - Scout Agent: New source discovery
  - Analyst Agent: (future) Trend detection, topic clustering

- **Leadership:**
  - CEO Agent "ALEX": Board communication, strategic decisions

**Agent Communication:**
- Agents communicate via standardized message protocol (JSON)
- LangGraph orchestrates complex multi-agent workflows
- Each agent has clear input/output contracts

---

### US-6: Graceful API Failure Handling
**As the** system  
**I want to** handle all API failures gracefully with fallbacks  
**So that** the pipeline never completely fails

**Acceptance Criteria:**
- Primary: Claude (Anthropic) for high-quality outputs
- Fallback 1: Groq (llama-3.1-8b-instant) for speed and reliability
- Fallback 2: Simple heuristics (score-based, rule-based) when LLMs fail
- All API calls logged with success/failure rates
- System reports API health to CEO Agent

**Current Bug:**
- Invalid Anthropic API key causing all Claude calls to fail
- System falling back to Groq but user didn't fix the key

---

### US-7: Daily and Weekly Digest Modes
**As a** board member  
**I want** both daily and weekly newsletter options  
**So that** I can choose digest frequency

**Acceptance Criteria:**
- DIGEST_MODE config: "daily" or "weekly"
- Daily: Last 24 hours of content
- Weekly: Last 7 days, with "Top Stories" editorial curation
- CEO Agent can switch modes based on board request

---

## Technical Requirements

### TR-1: Database Schema Updates
**Priority:** P0

**Required Changes:**
1. Add `sent_at` timestamp to clusters table
2. Add `digest_id` to track which digest included each cluster
3. Add `quality_score` field from QA Agent validation
4. Add `backup_used` boolean flag (if story was backup vs primary)

**Purpose:** Track sent content to prevent duplicates across runs

---

### TR-2: State Management System
**Priority:** P0

**Requirements:**
- Track all sent clusters/articles with timestamps
- Filter out sent content in subsequent runs
- Reset mechanism for testing (clear sent flags)
- Archive old sent content after 30 days

---

### TR-3: Agent Communication Protocol
**Priority:** P0

**Message Format:**
```json
{
  "from_agent": "qa_agent",
  "to_agent": "editor_agent",
  "action": "request_backup_stories",
  "reason": "primary_stories_failed_validation",
  "data": {
    "failed_cluster_ids": [1, 5, 9],
    "required_count": 3,
    "criteria": "importance_score >= 7.0"
  },
  "timestamp": "2026-08-08T12:00:00Z"
}
```

**Agent Registry:**
- Each agent registers capabilities and message handlers
- Coordinator routes messages between agents
- Async message queue for non-blocking operations

---

### TR-4: LangGraph Orchestration
**Priority:** P1 (after MVP)

**Purpose:** Handle complex multi-agent workflows

**Example Workflow: "Digest Generation"**
```
START
  ↓
[Ingest] → [Cleanup] → [Cluster] → [Summarize]
  ↓
[Reporter Agents] → Generate summaries in parallel
  ↓
[Fact-Checker] → Validate facts
  ↓
[QA Agent] → Validate dates & quality
  ↓
(If fails) → [Editor: Fetch Backups] → [QA Revalidate]
  ↓
[Editor-in-Chief] → Final story selection
  ↓
[Designer Agent] → Format HTML
  ↓
[QA Final Check] → Send or Retry
  ↓
END
```

---

### TR-5: Configuration Management
**Priority:** P0

**New Config Variables:**
```python
# Agent Configuration
CEO_AGENT_NAME = "ALEX"
ENABLE_SCOUT_AGENT = False  # P1 feature
AGENT_API_TIMEOUT = 30  # seconds

# Digest Configuration
DIGEST_MODE = "daily"  # or "weekly"
MAX_STORIES_PER_DIGEST = 20
MIN_STORIES_PER_DIGEST = 5  # Minimum required stories

# Quality Thresholds
MIN_QA_CONFIDENCE = 0.7
MIN_FACT_CHECK_SCORE = 0.6
ENABLE_BACKUP_STORIES = True

# State Management
MARK_AS_SENT_AFTER_DIGEST = True
ARCHIVE_SENT_AFTER_DAYS = 30
```

---

### TR-6: Error Handling & Observability
**Priority:** P0

**Requirements:**
1. **Logging:**
   - Structured JSON logs for machine parsing
   - Agent actions, decisions, failures all logged
   - Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

2. **Metrics:**
   - API success/failure rates per agent
   - Story validation pass/fail rates
   - Pipeline execution time per stage
   - Quality scores distribution

3. **Alerts:**
   - CEO Agent receives critical alerts
   - Board member notified only for P0 issues requiring strategic decisions
   - Self-healing attempts logged before escalation

---

### TR-7: API Key Management
**Priority:** P0

**Current Issue:** Invalid Anthropic API key

**Solution:**
1. Validate API keys on startup
2. Clear error messages if keys are invalid/placeholder
3. Graceful degradation to Groq if Claude unavailable
4. CEO Agent reports API health status

---

## Non-Functional Requirements

### NFR-1: Performance
- Pipeline completes in < 5 minutes for daily digest
- Each agent responds in < 30 seconds
- Database queries optimized for speed

### NFR-2: Reliability
- 99% uptime for autonomous operations
- Graceful degradation for all API failures
- No data loss on crashes (transactional updates)

### NFR-3: Scalability
- Support 100+ RSS feeds without performance degradation
- Agent system scales horizontally (can add more reporter agents)
- Database handles 1M+ articles efficiently

### NFR-4: Maintainability
- Each agent is self-contained module
- Clear interfaces between agents
- Comprehensive test coverage for critical paths
- Documentation for each agent's responsibilities

---

## Open Questions

### OQ-1: CEO Agent Communication Interface
**Question:** Should CEO Agent ALEX have:
- A) CLI chat interface (`python cli.py chat "What's today's performance?"`)
- B) Web dashboard (Next.js frontend)
- C) Slack/Discord bot integration
- D) All of the above (phased rollout)

**Recommendation:** Start with (A) CLI, then add (B) web dashboard

---

### OQ-2: Agent Personality & Branding
**Question:** Should agents have distinct personalities?
- Editor-in-Chief: Professional, decisive
- QA Agent: Meticulous, cautious
- CEO ALEX: Strategic, concise, board-level language

**Recommendation:** Yes—helps with system understandability and debugging

---

### OQ-3: Weekly Digest Editorial Strategy
**Question:** How should weekly digest differ from daily?
- A) Simple aggregation (all daily stories)
- B) "Best of" curation (top stories only)
- C) Trend analysis + top stories

**Recommendation:** (B) "Best of" curation—Editor Agent selects top 20 from week

---

## Success Metrics

### Operational Metrics
- **Zero Touch Operations:** 100% autonomous runs without intervention
- **Quality Score:** 95%+ stories pass QA validation on first attempt
- **Duplicate Rate:** 0% duplicate stories across runs
- **API Reliability:** 99%+ uptime across Claude + Groq fallback

### Business Metrics
- **Content Freshness:** 100% articles within LOOKBACK_HOURS window
- **Source Diversity:** Stories from 10+ different sources per digest
- **Newsletter Engagement:** (future) Open rates, click-through rates

### Agent Performance Metrics
- **QA Agent:** <1% false negative rate (missed old articles)
- **Editor Agent:** Story selection correlates with user engagement
- **Fact-Checker:** Cross-validation accuracy >95%
- **CEO Agent:** Response time <5 seconds for board queries

---

## Dependencies

### External Services
- Anthropic Claude API (primary LLM)
- Groq API (fallback LLM)
- RSS feed sources (35+ configured)
- SMTP server (email delivery)

### Python Packages
- anthropic, groq (LLM clients)
- feedparser (RSS parsing)
- sqlite3 (database)
- langgraph (agent orchestration) - P1
- pydantic (data validation)

### System Requirements
- Python 3.9+
- SQLite 3.35+
- Internet connectivity for APIs and RSS feeds

---

## Risks & Mitigations

### Risk 1: API Rate Limits
**Impact:** High  
**Probability:** Medium  
**Mitigation:** Implement exponential backoff, Groq fallback, request queuing

### Risk 2: All Agents Fail Simultaneously
**Impact:** Critical  
**Probability:** Low  
**Mitigation:** Fallback to rule-based heuristics, send error report to board member

### Risk 3: Database Corruption
**Impact:** Critical  
**Probability:** Low  
**Mitigation:** Daily backups, transactional updates, data validation on startup

### Risk 4: RSS Feeds Change Format
**Impact:** Medium  
**Probability:** Medium  
**Mitigation:** Scout Agent detects broken feeds, marks for manual review after 3 failures

---

## Out of Scope (Post-MVP)

1. **Next.js Web Dashboard** - P1 priority
2. **Real-time Updates** - WebSocket live feed
3. **Scout Agent** - Autonomous source discovery
4. **User Preferences** - Personalized digests per subscriber
5. **Multi-language Support** - Translations
6. **Mobile App** - Native iOS/Android apps
7. **Analytics Dashboard** - Detailed metrics visualization

---

## Appendix: Current System Issues (Must Fix)

### Critical (P0)
1. ✗ Invalid Anthropic API key causing all Claude calls to fail
2. ✗ QA Agent failure stops pipeline instead of fetching backups
3. ✗ Multiple runs showing same/old articles (state management)
4. ✗ No tracking of sent content across runs

### High (P1)
5. ✗ No CEO Agent for board communication
6. ✗ Agent coordination incomplete (no backup story mechanism)
7. ✗ No LangGraph orchestration
8. ✗ Error handling not resilient enough

### Medium (P2)
9. ✗ No Scout Agent for source discovery
10. ✗ No structured metrics/observability
11. ✗ Agent communication protocol not formalized

---

**Next Step:** Design document with architecture, agent workflows, and database schema.
