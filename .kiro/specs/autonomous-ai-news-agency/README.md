# Autonomous AI News Agency - Spec Overview

**Status:** Ready for Implementation  
**Created:** 2024-01-08  
**Estimated Timeline:** 3 weeks to MVP

---

## 📋 What This Spec Covers

This specification transforms your newsletter system into a **fully autonomous AI company** where every role—from CEO to reporter to QA tester—is handled by specialized AI agents.

### Current Problems Being Fixed:
1. ✗ **Invalid Anthropic API key** causing all Claude calls to fail
2. ✗ **QA Agent failure stops pipeline** instead of fetching backup stories
3. ✗ **Multiple runs show same/old articles** (no state management)
4. ✗ **Articles from June 2024 appearing** (date filtering not working across runs)
5. ✗ **No autonomous decision-making** (requires manual intervention)

### What You'll Get:
✅ **CEO Agent "ALEX"** - Your executive interface (you're the board member now)  
✅ **Zero duplicate content** - Running pipeline 2-3 times shows different news  
✅ **No old articles ever** - Strict date filtering with fallback mechanisms  
✅ **Resilient QA validation** - Fetches backup stories if validation fails  
✅ **Multi-agent coordination** - Editor, Reporter, QA, Fact-Checker all working autonomously  
✅ **Graceful API failures** - Claude → Groq → Heuristics fallback chain  
✅ **Complete observability** - All decisions logged, metrics tracked  

---

## 🏗️ Architecture Overview

```
BOARD MEMBER (You)
        ↓
   CEO Agent "ALEX" ←─ You only interact here
        ↓
   ┌────┴────┬────────────┬──────────┐
   ↓         ↓            ↓          ↓
EDITORIAL  QUALITY      TECH    INTELLIGENCE
   ↓         ↓                        ↓
Editor     QA Agent              Scout Agent
   ↓         ↓                    (Post-MVP)
Reporters  Fact-Checker
```

**Key Principle:** You make strategic decisions through CEO Agent. All operational work is autonomous.

---

## 📁 Spec Documents

### 1. [requirements.md](requirements.md)
**What it contains:**
- Business goals & user stories
- Technical requirements
- Success metrics
- Current bugs documented

**Key sections:**
- US-2: Zero duplicate content across runs
- US-3: Resilient QA validation with fallbacks
- US-6: Graceful API failure handling
- TR-2: State management system
- TR-3: Agent communication protocol

---

### 2. [design.md](design.md)
**What it contains:**
- System architecture diagrams
- Agent specifications (CEO, Editor, Reporter, QA, Fact-Checker)
- Database schema updates
- Pipeline workflows (happy path + failure recovery)
- API fallback chains

**Key sections:**
- Agent Specifications: Each agent's input/output contracts
- Workflow 2: QA validation fails → backup story mechanism
- Workflow 3: All API failures → degraded mode
- Database Schema: New tables for state management
- CEO Agent: Board communication interface

---

### 3. [tasks.md](tasks.md)
**What it contains:**
- Detailed implementation tasks (25 tasks total)
- Task dependencies graph
- Acceptance criteria per task
- 3-week rollout plan

**Key phases:**
- **Phase 1 (Week 1):** Fix critical issues (API keys, state management, QA backups)
- **Phase 2 (Week 2):** Multi-agent architecture (CEO, Editor, Reporter, Message Router)
- **Phase 3 (Week 3):** Observability, testing, documentation
- **Phase 4 (Future):** Scout Agent, LangGraph, Web dashboard

---

## 🚀 Quick Start (For Implementation)

### Step 1: Fix Critical Issues (Phase 1)
Start with these tasks in order:
1. **Task 1.1:** API Key Validation - Fix the Anthropic key issue
2. **Task 1.2:** Database Migration - Add sent_at, digest_id columns
3. **Task 1.3:** State Manager - Track sent content
4. **Task 1.4:** Filter sent content in cleanup stage
5. **Task 1.5:** QA backup mechanism

**Result:** System works reliably, no duplicates

---

### Step 2: Build Multi-Agent System (Phase 2)
Implement agents in this order:
1. **Task 2.1:** Message Router - Agent communication protocol
2. **Task 2.2:** CEO Agent - ALEX for board communication
3. **Task 2.3:** CEO CLI - Command-line interface
4. **Task 2.4:** Reporter Agents - Beat-based (Company News, Research, Tools)
5. **Task 2.5:** Fact-Checker - Enhanced validation
6. **Task 2.6:** Refactor coordinator - Integrate all agents

**Result:** Fully autonomous multi-agent company

---

### Step 3: Polish & Test (Phase 3)
Add observability and testing:
1. **Task 3.1-3.4:** Logging, metrics, degraded mode, error handling
2. **Task 4.1-4.2:** Unit tests + integration tests
3. **Task 4.3:** Documentation updates

**Result:** Production-ready system

---

## 💡 Key Innovations

### 1. Backup Story Mechanism (US-3)
**Problem:** QA Agent fails → pipeline stops → no newsletter  
**Solution:** QA Agent requests backup stories from Editor Agent

```
QA validates → 3 stories fail → QA asks Editor for 3 backups
→ Editor fetches next-best 3 stories → QA revalidates
→ Digest uses valid + backup stories → Success!
```

---

### 2. State Management (US-2)
**Problem:** Running pipeline 2-3 times shows same stories  
**Solution:** Track sent clusters with `sent_at` timestamp

```
Run 1: Stories [1-15] sent → Mark as sent (sent_at = now)
Run 2: Filter out sent stories → Stories [16-30] sent
Run 3: Filter out sent stories → Stories [31-45] sent
```

---

### 3. CEO Agent Interface
**Problem:** User has to read technical logs to understand system  
**Solution:** CEO Agent translates to executive language

```bash
# Instead of reading logs:
$ python ceo_cli.py status
Today's Digest Performance:
✓ 15 stories published from 12 sources
✓ Quality score: 8.5/10
✓ All API calls successful
✓ Zero issues requiring attention
```

---

### 4. Triple Fallback Chain
**Problem:** API failures kill pipeline  
**Solution:** Claude → Groq → Heuristics

```
Try Claude → Fail (401)
Try Groq → Fail (rate limit)
Use heuristics (first paragraph, date sorting)
→ Digest still generated (lower quality, but never fails)
```

---

## 🎯 Success Criteria

### Must Have (Before Release):
- [ ] No duplicate content across multiple runs
- [ ] No old articles (before 2026-07-01) ever appear
- [ ] QA Agent requests backups when validation fails
- [ ] CEO Agent responds to board queries
- [ ] All API failures handled gracefully
- [ ] Integration tests pass

### Performance Targets:
- Pipeline completes in < 5 minutes
- Agent response time < 30 seconds each
- API success rate > 95% (with fallbacks)
- Zero pipeline crashes

---

## 📊 Implementation Timeline

```
Week 1: Phase 1 (Critical Fixes)
├─ Mon-Tue: API validation, DB migration, state manager
├─ Wed-Thu: Cleanup filter, QA backup mechanism
└─ Friday: Integration testing

Week 2: Phase 2 (Multi-Agent)
├─ Mon-Tue: Message router, CEO Agent, CLI
├─ Wed-Thu: Reporter agents, fact-checker
└─ Friday: Refactor coordinator, integration

Week 3: Phase 3 & 4 (Polish)
├─ Mon-Tue: Logging, metrics, degraded mode
├─ Wed-Thu: Unit + integration tests
└─ Friday: Documentation, final testing

✅ PRODUCTION READY
```

---

## 🔧 Configuration Changes

### New Variables in config.py:
```python
# Agent Configuration
CEO_AGENT_NAME = "ALEX"
ENABLE_REPORTER_AGENTS = True
REPORTER_COUNT = 3

# Digest Configuration
DIGEST_MODE = "daily"  # or "weekly"
TOP_N_STORIES = 15
MIN_STORIES_PER_DIGEST = 5

# Quality Thresholds
MIN_IMPORTANCE_SCORE = 7.0
MIN_QA_CONFIDENCE = 0.7
ENABLE_BACKUP_STORIES = True

# State Management
MARK_AS_SENT_AFTER_DIGEST = True
ARCHIVE_SENT_AFTER_DAYS = 30
```

---

## 📂 New Files Created

```
agents/
├── ceo_agent.py           # CEO Agent ALEX
├── editor_agent.py        # Editorial decisions
├── reporter_agent.py      # Beat-based reporters
├── fact_checker_agent.py  # Enhanced validation
├── message_router.py      # Agent communication
└── state_manager.py       # Sent content tracking

ceo_cli.py                 # Board member CLI
db_migrate.py              # Database migration script

utils/
├── api_validator.py       # API key validation
├── agent_logger.py        # Structured logging
└── metrics_collector.py   # Performance metrics

tests/
├── test_agents.py         # Agent unit tests
└── test_pipeline.py       # Integration tests
```

---

## 🤝 How to Use This Spec

### For Implementation:
1. Read [requirements.md](requirements.md) to understand the "why"
2. Read [design.md](design.md) to understand the "how"
3. Follow [tasks.md](tasks.md) for step-by-step implementation
4. Start with Phase 1 (Week 1) - critical fixes

### For Review:
- Check requirements.md for business goals alignment
- Review design.md for architecture decisions
- Validate tasks.md for completeness

### For Testing:
- Use acceptance criteria in tasks.md
- Run integration tests from Phase 4
- Validate against success criteria in requirements.md

---

## 🎓 Learning Resources

### Agent Architecture:
- [LangGraph Documentation](https://python.langchain.com/docs/langgraph) - Multi-agent orchestration
- [Anthropic Claude Docs](https://docs.anthropic.com/) - Primary LLM
- [Groq API Docs](https://console.groq.com/docs) - Fallback LLM

### Design Patterns:
- **Message Passing:** Inter-agent communication
- **Circuit Breaker:** API failure handling
- **Chain of Responsibility:** Fallback chains
- **State Pattern:** Sent content tracking

---

## 🐛 Known Issues & Fixes

| Issue | Root Cause | Fix (Task) |
|-------|-----------|------------|
| Duplicate stories across runs | No sent content tracking | Task 1.3 (State Manager) |
| Old articles appearing | State not filtered in cleanup | Task 1.4 (Filter sent) |
| QA failure stops pipeline | No backup mechanism | Task 1.5 (QA backups) |
| Invalid Anthropic API key | No validation on startup | Task 1.1 (API validation) |
| Pipeline crashes on API failure | No fallback chain | Task 3.4 (Error handling) |

---

## 🙋 FAQs

**Q: Will this replace the current system completely?**  
A: Yes, but it's backward compatible. Phase 1 fixes critical issues in existing code. Phase 2 adds agents on top.

**Q: Can I still run the pipeline manually?**  
A: Yes! `python main.py` works as before. CEO Agent is optional for queries.

**Q: What if I want to see technical details, not just CEO summaries?**  
A: Use `ceo_cli.py status --detailed` or check agent_logs table directly.

**Q: How do I test without breaking production?**  
A: Set `DIGEST_TEST_MODE=1` to save to file instead of sending emails.

**Q: Can I add my own agents later?**  
A: Absolutely! Follow the extension guide in agents/README.md.

---

## ✅ Next Steps

1. **Review this spec** - Make sure it aligns with your vision
2. **Start Phase 1** - Begin with Task 1.1 (API validation)
3. **Test continuously** - Use test mode for safety
4. **Monitor progress** - Track against success criteria

---

**Ready to build?** Start with [tasks.md](tasks.md) → Phase 1 → Task 1.1

**Questions?** Interact with CEO Agent ALEX once implemented: `python ceo_cli.py ask "your question"`

**Want to understand architecture deeper?** Read [design.md](design.md)

**Need business justification?** Show [requirements.md](requirements.md) to stakeholders
