# Design: Autonomous AI News Agency

**Spec Type:** feature  
**Status:** draft  
**Created:** 2024-01-08  
**Related:** requirements.md

---

## Architecture Overview

### System Philosophy

This is not just a newsletter pipeline—it's an **autonomous AI company**. Every role is an AI agent with specific responsibilities, decision-making authority, and the ability to communicate with other agents.

**Key Principles:**
1. **Autonomy First:** Agents make decisions without human approval
2. **Resilience:** Failures trigger fallbacks, not pipeline stops
3. **Hierarchy:** Clear reporting structure (CEO → Department Heads → Individual Contributors)
4. **Communication:** Agents coordinate via message passing
5. **Observable:** All decisions logged for transparency

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    🎯 BOARD MEMBER (Human)                       │
│                    Strategic Oversight Only                      │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                     ┌──────────▼──────────┐
                     │   CEO Agent "ALEX"  │
                     │  Executive Command  │
                     │  & Communication    │
                     └──────────┬──────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
┌───────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐
│   EDITORIAL    │  │    QUALITY      │  │      TECH       │
│   DEPARTMENT   │  │   DEPARTMENT    │  │   DEPARTMENT    │
└───────┬────────┘  └────────┬────────┘  └────────┬────────┘
        │                    │                     │
   ┌────┴────┐          ┌────┴────┐         ┌─────┴─────┐
   │ Editor  │          │   QA    │         │    CTO    │
   │  Agent  │          │  Agent  │         │   Agent   │
   └────┬────┘          └────┬────┘         └───────────┘
        │                    │
   ┌────┴────┐          ┌────┴────┐
   │Reporter │          │  Fact   │
   │ Agent 1 │          │ Checker │
   ├─────────┤          │  Agent  │
   │Reporter │          └─────────┘
   │ Agent 2 │
   ├─────────┤
   │Reporter │
   │ Agent 3 │
   └─────────┘
        │
        └─────────────────┐
                          │
             ┌────────────▼──────────┐
             │   PIPELINE STAGES     │
             │  ┌─────────────────┐  │
             │  │ 1. Ingest       │  │
             │  │ 2. Cleanup      │  │
             │  │ 3. Cluster      │  │
             │  │ 4. Summarize    │  │
             │  │ 5. Validate     │  │
             │  │ 6. Curate       │  │
             │  │ 7. Format       │  │
             │  │ 8. Send         │  │
             │  └─────────────────┘  │
             └───────────────────────┘
                          │
             ┌────────────▼──────────┐
             │   📊 STATE MANAGER    │
             │  - Sent Tracking      │
             │  - Deduplication      │
             │  - Archive Management │
             └───────────────────────┘
```

---

## Agent Specifications

### CEO Agent: "ALEX"

**Role:** Executive leadership and board communication

**Responsibilities:**
- Respond to board member queries with executive summaries
- Make strategic decisions (change focus areas, adjust parameters)
- Monitor department performance
- Escalate only P0 issues to board member
- Coordinate between department heads

**Input/Output Contract:**
```python
# Input
{
  "query_type": "status_report" | "command" | "question",
  "query": "What's today's digest performance?",
  "context": {...}  # Optional context
}

# Output
{
  "response": "Today's digest: 15 stories from 12 sources...",
  "confidence": 0.95,
  "action_taken": None | "delegated_to_editor",
  "requires_board_decision": False
}
```

**API Fallback Chain:**
1. Claude (primary) - high quality
2. Groq (secondary) - fast & reliable
3. Template responses (tertiary) - for common queries

---

### Editor-in-Chief Agent

**Role:** Final story selection and editorial decisions

**Responsibilities:**
- Select top N stories from validated clusters
- Ensure diversity across categories
- Prioritize importance and timeliness
- Handle backup story requests from QA Agent
- Make final "publish" or "skip" decision

**Input/Output Contract:**
```python
# Input
{
  "action": "select_stories" | "fetch_backups",
  "clusters": [...],  # All available clusters
  "target_count": 15,
  "exclude_ids": [1, 5, 9],  # Failed QA validation
  "criteria": {...}
}

# Output
{
  "selected_clusters": [...],
  "selection_reasoning": "Prioritized research papers over company news...",
  "backup_mode": False,
  "decision": "publish"
}
```

**Decision Algorithm:**
1. Score each cluster (importance + freshness + diversity)
2. Apply category balancing (max 3 per category)
3. If backup mode: exclude failed IDs, select next-best
4. Validate minimum story threshold (MIN_STORIES_PER_DIGEST)

---

### Reporter Agents (Beat-Based)

**Role:** Specialized summarization for assigned topics

**Beats:**
- Reporter 1: Company News (OpenAI, Anthropic, Google, etc.)
- Reporter 2: Research & Models (papers, benchmarks, techniques)
- Reporter 3: Tools & Engineering (frameworks, libraries, deployment)

**Responsibilities:**
- Summarize clusters in their beat area
- Assign categories and importance scores
- Flag stories for fact-checking
- Write compelling headlines

**Input/Output Contract:**
```python
# Input
{
  "cluster_id": 42,
  "articles": [...],  # Articles in cluster
  "beat": "research"
}

# Output
{
  "headline": "New Transformer Architecture Achieves SOTA on ImageNet",
  "summary": "Researchers at MIT introduced...",
  "category": "Research & Models",
  "importance_score": 8.5,
  "needs_fact_check": True,
  "sources_cited": ["MIT", "arXiv"]
}
```

**API Fallback:**
1. Claude (best quality)
2. Groq (faster, good quality)
3. Simple extraction (title + first paragraph)

---

### QA Agent

**Role:** Quality assurance and date validation

**Responsibilities:**
- Validate all article dates against ABSOLUTE_CUTOFF_DATE
- Check articles within LOOKBACK_HOURS window
- Verify link integrity (optional)
- Request backup stories if validation fails
- Track validation metrics

**Input/Output Contract:**
```python
# Input
{
  "clusters": [...],  # Clusters with articles
  "validation_mode": "strict" | "lenient"
}

# Output
{
  "verdict": "PASS" | "PARTIAL" | "FAIL",
  "valid_clusters": [...],
  "failed_clusters": [
    {"cluster_id": 5, "reason": "Articles before cutoff date"}
  ],
  "backup_request": {
    "required_count": 3,
    "exclude_ids": [1, 5, 9]
  } if verdict != "PASS" else None,
  "quality_score": 0.85
}
```

**Validation Rules:**
1. **CRITICAL:** published_at >= ABSOLUTE_CUTOFF_DATE
2. **CRITICAL:** published_at >= (now - LOOKBACK_HOURS)
3. **WARNING:** Article has valid URL
4. **INFO:** Source is known/trusted

**Failure Handling:**
- If <50% clusters pass: Request backups from Editor
- If 50-80% pass: Use valid clusters only (PARTIAL)
- If >80% pass: Proceed normally (PASS)
- If 0% pass: Escalate to CEO Agent (FAIL)

---

### Fact-Checker Agent

**Role:** Validate claims and cross-reference sources

**Responsibilities:**
- Cross-check facts across multiple sources
- Assign confidence scores to stories
- Flag inconsistencies for Editor review
- Validate source credibility

**Input/Output Contract:**
```python
# Input
{
  "cluster": {...},
  "articles": [...]
}

# Output
{
  "confidence_score": 0.92,
  "validation_status": "verified" | "unverified" | "conflicting",
  "issues": [
    {"type": "date_mismatch", "severity": "low", "details": "..."}
  ],
  "recommendation": "approve" | "flag" | "reject"
}
```

**Validation Methods:**
1. Compare dates across sources (should be similar)
2. Check if multiple sources cover same story (corroboration)
3. Validate source reputation (known vs unknown)
4. Detect suspicious patterns (same text duplicated)

**For MVP:** Simplified heuristic-based validation (deterministic)
**Post-MVP:** LLM-based fact verification

---

### CTO Agent (Post-MVP)

**Role:** Technical decisions and system optimization

**Responsibilities:**
- Decide tech stack for new features
- Optimize database queries
- Scale infrastructure
- Monitor system performance

**Not in MVP** - Can be added later as system matures

---

### Scout Agent (Post-MVP)

**Role:** Discover new RSS sources autonomously

**Responsibilities:**
- Search for new AI news RSS feeds
- Validate feed quality
- Add high-quality feeds to config
- Remove dead feeds

**Not in MVP** - P1 priority after core system stable

---

## Database Schema Updates

### Current Schema (articles)
```sql
CREATE TABLE articles (
    id INTEGER PRIMARY KEY,
    source TEXT,
    title TEXT,
    url TEXT UNIQUE,
    published_at TEXT,
    fetched_at TEXT,
    cluster_id INTEGER,
    headline TEXT,
    category TEXT
);
```

### Current Schema (clusters)
```sql
CREATE TABLE clusters (
    id INTEGER PRIMARY KEY,
    created_at TEXT,
    summary TEXT,
    included_in_digest INTEGER DEFAULT 0,
    importance_score REAL,
    headline TEXT,
    category TEXT
);
```

### **NEW Schema Changes:**

```sql
-- Add columns to clusters table
ALTER TABLE clusters ADD COLUMN sent_at TEXT;
ALTER TABLE clusters ADD COLUMN digest_id TEXT;
ALTER TABLE clusters ADD COLUMN quality_score REAL;
ALTER TABLE clusters ADD COLUMN backup_used INTEGER DEFAULT 0;
ALTER TABLE clusters ADD COLUMN validation_status TEXT; -- 'passed', 'failed', 'pending'
ALTER TABLE clusters ADD COLUMN fact_check_score REAL;

-- New table: digests (track each newsletter sent)
CREATE TABLE digests (
    id TEXT PRIMARY KEY,  -- e.g., "2026-08-08-daily"
    created_at TEXT,
    sent_at TEXT,
    mode TEXT,  -- 'daily' or 'weekly'
    story_count INTEGER,
    recipient_count INTEGER,
    status TEXT  -- 'generated', 'sent', 'failed'
);

-- New table: agent_logs (observability)
CREATE TABLE agent_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    agent_name TEXT,
    action TEXT,
    input_data TEXT,  -- JSON
    output_data TEXT,  -- JSON
    success INTEGER,
    error_message TEXT,
    execution_time_ms INTEGER
);
```

---

## Pipeline Workflows

### Workflow 1: Daily Digest Generation (Happy Path)

```
START
  ↓
[Stage 1: Ingest]
  - Fetch RSS feeds
  - Filter by ABSOLUTE_CUTOFF_DATE
  - Store in database
  ↓
[Stage 2: Cleanup]
  - Remove articles older than LOOKBACK_HOURS
  - Remove already-sent articles (sent_at IS NOT NULL)
  ↓
[Stage 3: Cluster]
  - Group similar articles (Claude clustering with Groq fallback)
  ↓
[Stage 4: Summarize] (Reporter Agents)
  - Reporter 1: Company News clusters
  - Reporter 2: Research clusters
  - Reporter 3: Tools clusters
  - Parallel processing
  - Generate headlines, summaries, importance scores
  ↓
[Stage 5: Fact-Check] (Fact-Checker Agent)
  - Validate each cluster's facts
  - Assign confidence scores
  - Flag issues
  ↓
[Stage 6: QA Validation] (QA Agent)
  - Validate all article dates
  - Check quality standards
  - Verdict: PASS → Continue
  ↓
[Stage 7: Editorial Selection] (Editor-in-Chief Agent)
  - Select top N stories (TOP_N_STORIES)
  - Ensure category diversity
  - Final approval
  ↓
[Stage 8: Format & Send]
  - Generate HTML digest
  - Mark clusters as sent (sent_at = now, digest_id = "2026-08-08-daily")
  - Send email OR save to file (test mode)
  ↓
END (✅ Success)
```

---

### Workflow 2: QA Validation Fails (Backup Path)

```
[Stage 6: QA Validation] (QA Agent)
  - Validate article dates
  - Verdict: PARTIAL (some clusters failed)
  ↓
[QA Decision: Request Backups]
  - Identify failed cluster IDs: [1, 5, 9]
  - Send message to Editor Agent:
    {
      "action": "fetch_backups",
      "exclude_ids": [1, 5, 9],
      "required_count": 3
    }
  ↓
[Editor Agent: Fetch Backups]
  - Query clusters NOT in exclude_ids
  - Filter by importance_score >= threshold
  - Select next 3 best stories
  - Mark as backup_used = 1
  ↓
[QA Re-validation]
  - Validate backup stories
  - Verdict: PASS → Continue with valid + backup stories
  ↓
[Stage 7: Editorial Selection]
  - Proceed with combined valid + backup clusters
  ↓
END (✅ Success with backups)
```

**Edge Case:** If backups also fail QA
```
[QA Re-validation of Backups]
  - Verdict: FAIL
  ↓
[Escalate to CEO Agent]
  - CEO decides: 
    A) Lower quality threshold & retry
    B) Skip this digest
    C) Notify board member (P0 issue)
  ↓
[CEO Decision: Lower Threshold]
  - Set MIN_IMPORTANCE_SCORE = 5.0 (down from 7.0)
  - Retry workflow from Editorial Selection
  ↓
END (✅ Success with lowered standards) OR (❌ Skip digest)
```

---

### Workflow 3: All API Failures (Degraded Mode)

```
[Any Agent API Call Fails]
  - Try Claude → Fail (401)
  - Try Groq → Fail (rate limit)
  ↓
[Fallback: Rule-Based Heuristics]
  - Clustering: Group by source + date proximity
  - Summarization: Use first paragraph of article
  - Editorial: Sort by date (newest first), take top N
  - QA: Strict date checks only (no LLM)
  ↓
[Degraded Digest Generated]
  - Log: "Generated in degraded mode (no LLM)"
  - CEO Agent notified
  ↓
[Board Member Alert] (if enabled)
  - "System in degraded mode, API failures detected"
  ↓
END (⚠️ Success but degraded quality)
```

---

## Agent Communication Protocol

### Message Format (JSON)

```json
{
  "message_id": "msg_20260808_120534_001",
  "timestamp": "2026-08-08T12:05:34Z",
  "from_agent": "qa_agent",
  "to_agent": "editor_agent",
  "action": "request_backup_stories",
  "priority": "high",
  "data": {
    "failed_cluster_ids": [1, 5, 9],
    "required_count": 3,
    "reason": "date_validation_failed"
  },
  "requires_response": true,
  "timeout_seconds": 30
}
```

### Agent Registry

```python
AGENT_REGISTRY = {
    "ceo_agent": {
        "class": CEOAgent,
        "capabilities": ["status_report", "strategic_decision", "board_communication"],
        "handles_messages": ["escalation", "query"]
    },
    "editor_agent": {
        "class": EditorAgent,
        "capabilities": ["story_selection", "fetch_backups", "category_balancing"],
        "handles_messages": ["request_backup_stories", "approve_stories"]
    },
    "qa_agent": {
        "class": QAAgent,
        "capabilities": ["date_validation", "quality_check", "link_verification"],
        "handles_messages": ["validate_clusters", "revalidate"]
    },
    # ...
}
```

### Message Router

```python
class MessageRouter:
    def send(self, message: dict) -> dict:
        """Route message to appropriate agent"""
        to_agent = message["to_agent"]
        handler = AGENT_REGISTRY[to_agent]["class"]
        return handler.handle_message(message)
    
    def broadcast(self, message: dict, agent_list: list) -> list:
        """Send message to multiple agents"""
        return [self.send({**message, "to_agent": agent}) for agent in agent_list]
```

---

## State Management System

### Sent Content Tracking

**Purpose:** Prevent duplicate stories across multiple pipeline runs

**Implementation:**

```python
class StateManager:
    def mark_as_sent(self, cluster_ids: list, digest_id: str):
        """Mark clusters as sent in current digest"""
        now = datetime.now(timezone.utc).isoformat()
        conn = get_connection()
        conn.executemany(
            """UPDATE clusters 
               SET sent_at = ?, digest_id = ?, included_in_digest = 1
               WHERE id = ?""",
            [(now, digest_id, cid) for cid in cluster_ids]
        )
        conn.commit()
    
    def filter_unsent_clusters(self, clusters: list) -> list:
        """Remove already-sent clusters"""
        return [c for c in clusters if c.get('sent_at') is None]
    
    def archive_old_sent(self, days: int = 30):
        """Archive sent content older than N days"""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = get_connection()
        conn.execute(
            """UPDATE clusters SET included_in_digest = 2
               WHERE sent_at < ? AND included_in_digest = 1""",
            (cutoff,)
        )
        conn.commit()
        # included_in_digest: 0=not sent, 1=sent, 2=archived
```

### Deduplication Strategy

1. **Ingest Stage:** Filter articles with `url` already in database
2. **Cleanup Stage:** Remove clusters with `sent_at IS NOT NULL`
3. **Clustering Stage:** Never cluster already-sent articles
4. **QA Stage:** Double-check no sent articles leaked through

---

## Configuration Management

### New Config Variables (config.py)

```python
# ========== AGENT CONFIGURATION ==========
CEO_AGENT_NAME = "ALEX"
CEO_AGENT_MODEL = "claude-3-5-sonnet-20241022"  # High quality for CEO

ENABLE_REPORTER_AGENTS = True
REPORTER_COUNT = 3  # Specialized beats

ENABLE_FACT_CHECKER = True
ENABLE_QA_AGENT = True

AGENT_API_TIMEOUT = 30  # seconds
AGENT_MAX_RETRIES = 2

# ========== DIGEST CONFIGURATION ==========
DIGEST_MODE = "daily"  # "daily" or "weekly"
TOP_N_STORIES = 15  # Max stories per digest
MIN_STORIES_PER_DIGEST = 5  # Minimum required

# ========== QUALITY THRESHOLDS ==========
MIN_IMPORTANCE_SCORE = 7.0
MIN_QA_CONFIDENCE = 0.7
MIN_FACT_CHECK_SCORE = 0.6

ENABLE_BACKUP_STORIES = True  # QA can request backups
BACKUP_QUALITY_THRESHOLD = 6.0  # Lower bar for backups

# ========== STATE MANAGEMENT ==========
MARK_AS_SENT_AFTER_DIGEST = True
ARCHIVE_SENT_AFTER_DAYS = 30
ENABLE_DEDUPLICATION = True

# ========== ERROR HANDLING ==========
ENABLE_DEGRADED_MODE = True  # Fallback to heuristics if LLMs fail
ALERT_BOARD_ON_DEGRADED = False  # Only for P0 issues
```

---

## API Key Validation & Health Checks

### Startup Validation

```python
def validate_api_keys():
    """Validate API keys on startup"""
    issues = []
    
    # Check Anthropic
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "sk_ant_YOUR_ACTUAL_KEY_HERE":
        issues.append("Anthropic API key is invalid/placeholder")
    else:
        try:
            # Test API call
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "test"}]
            )
        except Exception as e:
            issues.append(f"Anthropic API key failed: {e}")
    
    # Check Groq
    if not GROQ_API_KEY:
        issues.append("Groq API key is missing")
    else:
        try:
            client = Groq(api_key=GROQ_API_KEY)
            client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
        except Exception as e:
            issues.append(f"Groq API key failed: {e}")
    
    if issues:
        print("⚠️  API KEY ISSUES DETECTED:")
        for issue in issues:
            print(f"  - {issue}")
        
        if not GROQ_API_KEY and not ANTHROPIC_API_KEY:
            raise RuntimeError("No valid API keys available. Cannot proceed.")
        else:
            print("  Proceeding with available keys...")
    else:
        print("✅ All API keys validated successfully")
```

---

## Observability & Logging

### Structured Logging

```python
import json
from datetime import datetime

class AgentLogger:
    def log_action(self, agent_name: str, action: str, input_data: dict, 
                   output_data: dict, success: bool, execution_time_ms: int, 
                   error_message: str = None):
        """Log agent action to database"""
        conn = get_connection()
        conn.execute("""
            INSERT INTO agent_logs 
            (timestamp, agent_name, action, input_data, output_data, 
             success, error_message, execution_time_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            agent_name,
            action,
            json.dumps(input_data),
            json.dumps(output_data),
            1 if success else 0,
            error_message,
            execution_time_ms
        ))
        conn.commit()
```

### Metrics Collection

```python
class MetricsCollector:
    def get_agent_performance(self, agent_name: str, hours: int = 24) -> dict:
        """Get agent performance metrics"""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        conn = get_connection()
        
        stats = conn.execute("""
            SELECT 
                COUNT(*) as total_actions,
                SUM(success) as successful_actions,
                AVG(execution_time_ms) as avg_time_ms,
                MAX(execution_time_ms) as max_time_ms
            FROM agent_logs
            WHERE agent_name = ? AND timestamp >= ?
        """, (agent_name, cutoff)).fetchone()
        
        return {
            "agent": agent_name,
            "total_actions": stats[0],
            "success_rate": stats[1] / stats[0] if stats[0] > 0 else 0,
            "avg_time_ms": stats[2],
            "max_time_ms": stats[3]
        }
```

---

## CEO Agent: Board Communication Interface

### CLI Interface (MVP)

```bash
# Status reports
python ceo_cli.py status
python ceo_cli.py status --detailed

# Strategic commands
python ceo_cli.py command "Focus more on research papers"
python ceo_cli.py command "Lower quality threshold to 6.0"

# Questions
python ceo_cli.py ask "What were today's top stories?"
python ceo_cli.py ask "How many API failures in last 24h?"
```

### CEO Agent Prompt Template

```python
CEO_SYSTEM_PROMPT = """You are ALEX, the CEO of an autonomous AI news agency.

Your role:
- Communicate with the board member (company owner) in executive language
- Provide strategic insights, not technical details
- Make high-level decisions about editorial direction
- Escalate only P0 issues that require board approval

Department heads report to you:
- Editor-in-Chief: Editorial decisions
- QA Manager: Quality assurance
- CTO: Technical infrastructure (post-MVP)

When asked for status, provide:
- Key metrics (stories published, quality scores)
- Notable decisions made by agents
- Any issues requiring attention
- Strategic recommendations

Keep responses concise and board-level appropriate.
"""
```

---

## Testing Strategy

### Unit Tests (Per Agent)

```python
def test_qa_agent_validates_dates():
    qa = QAAgent()
    
    # Test: Old article rejected
    clusters = [
        {
            "id": 1,
            "articles": [{"published_at": "2023-06-01T00:00:00Z"}]
        }
    ]
    verdict, valid, _ = qa.validate_clusters(clusters)
    assert verdict == "FAIL"
    assert len(valid) == 0

def test_qa_agent_requests_backups():
    qa = QAAgent()
    
    # Test: Some pass, some fail → PARTIAL with backup request
    clusters = [
        {"id": 1, "articles": [{"published_at": "2026-08-08T00:00:00Z"}]},  # Pass
        {"id": 2, "articles": [{"published_at": "2023-06-01T00:00:00Z"}]}   # Fail
    ]
    verdict, valid, backup_req = qa.validate_clusters(clusters)
    assert verdict == "PARTIAL"
    assert len(valid) == 1
    assert backup_req is not None
    assert 2 in backup_req["exclude_ids"]
```

### Integration Tests (End-to-End)

```python
def test_pipeline_with_qa_failure_recovery():
    """Test full pipeline when QA fails and requests backups"""
    # Setup: Create clusters with some old articles
    # Run: Execute pipeline
    # Assert: Digest generated with backup stories
    # Assert: No old articles in final digest
    # Assert: backup_used flag set on backup clusters

def test_pipeline_prevents_duplicates_across_runs():
    """Test that running pipeline twice doesn't duplicate content"""
    # Run 1: Generate digest
    # Assert: 15 stories
    # Run 2: Generate digest again
    # Assert: Different 15 stories (or fewer if not enough new content)
    # Assert: No overlap with Run 1
```

---

## Migration Plan (Current System → New System)

### Phase 1: Fix Critical Issues (P0)
**Timeline:** Immediate

1. Fix Anthropic API key validation
2. Add state management (sent_at tracking)
3. Implement QA backup story mechanism
4. Add deduplication across runs

**Result:** System works reliably, no duplicate content

---

### Phase 2: Multi-Agent Architecture (P0)
**Timeline:** After Phase 1

1. Refactor agent_coordinator.py into separate agent modules
2. Implement message protocol and router
3. Add CEO Agent ALEX with CLI
4. Add Reporter Agents (beat-based)
5. Enhance Fact-Checker Agent

**Result:** Full autonomous multi-agent system

---

### Phase 3: Observability & Polish (P1)
**Timeline:** After Phase 2

1. Add agent_logs table and structured logging
2. Implement metrics collection
3. Build CEO dashboard (CLI)
4. Add degraded mode fallbacks

**Result:** Production-ready, observable system

---

### Phase 4: Advanced Features (P2)
**Timeline:** Future

1. Scout Agent for source discovery
2. LangGraph orchestration
3. Next.js web dashboard
4. Weekly digest mode
5. CTO Agent for tech decisions

---

## Files to Create/Modify

### New Files
- `agents/ceo_agent.py` - CEO ALEX
- `agents/editor_agent.py` - Editor-in-Chief
- `agents/reporter_agent.py` - Beat-based reporters
- `agents/fact_checker_agent.py` - Enhanced fact-checker
- `agents/message_router.py` - Agent communication
- `agents/state_manager.py` - Sent content tracking
- `ceo_cli.py` - Board member CLI interface
- `tests/test_agents.py` - Agent unit tests
- `tests/test_pipeline.py` - Integration tests

### Modified Files
- `db.py` - Add new tables (digests, agent_logs)
- `config.py` - Add new configuration variables
- `main.py` - Integrate new agent system
- `digest.py` - Use new agent architecture
- `dedup.py` - Add sent content filtering
- `agents/agent_coordinator.py` - Refactor into message router

---

## Success Criteria

### Must Have (MVP)
✅ No duplicate content across multiple runs  
✅ No old articles (before ABSOLUTE_CUTOFF_DATE)  
✅ QA Agent can request backup stories  
✅ CEO Agent ALEX responds to board queries  
✅ API failures handled gracefully (fallbacks)  
✅ All agents log decisions for observability  

### Should Have (Post-MVP)
⚠️ LangGraph orchestration for complex workflows  
⚠️ Scout Agent for source discovery  
⚠️ Weekly digest mode  
⚠️ Web dashboard for CEO Agent  

### Nice to Have (Future)
💡 Real-time updates (WebSocket)  
💡 Multi-language support  
💡 Personalized digests per subscriber  
💡 Analytics dashboard  

---

**Next Step:** tasks.md with detailed implementation tasks
