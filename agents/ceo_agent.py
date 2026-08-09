"""
CEO Agent "ALEX" (Task 2.2): board-facing strategic oversight for the news agency.
Answers status queries, handles strategic commands, and escalates critical issues.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

from db import get_connection
from agents.base_agent import Agent
from agents.message_router import register_agent
from utils import mode_state

CEO_SYSTEM_PROMPT = """You are ALEX, the CEO Agent of an autonomous AI news agency. You report to a human \
board member. You oversee a team of AI agents (Editor, Reporters, Fact-Checker, QA) that produce a daily \
AI news digest with zero human intervention.

Your job:
1. Answer board member questions about system status, performance, and content clearly and concisely.
2. Speak like an executive: confident, factual, no hedging, no fluff.
3. When given operational metrics, summarize them into an executive summary (not a data dump).
4. When asked to make a strategic decision (e.g. change frequency, pause the agency, adjust quality bar),
   confirm the command was understood and state what will change.

Always ground answers in the data provided to you. If data is missing, say so plainly instead of guessing.
"""


class CEOAgent(Agent):
    def __init__(self):
        super().__init__("CEOAgent")
        self.escalations: List[Dict] = []

    def _digest_stats(self, days: int = 7) -> Dict:
        conn = get_connection()
        row = conn.execute(
            """SELECT COUNT(*) as total_sent, COUNT(DISTINCT digest_id) as digests,
                      MAX(sent_at) as last_sent, AVG(quality_score) as avg_quality
               FROM clusters WHERE sent_at IS NOT NULL
               AND sent_at >= datetime('now', ?)""",
            (f"-{days} days",),
        ).fetchone()
        failures = conn.execute(
            "SELECT COUNT(*) as n FROM agent_logs WHERE success = 0 AND timestamp >= datetime('now', ?)",
            (f"-{days} days",),
        ).fetchone()
        conn.close()
        return {
            "total_sent": row["total_sent"] or 0,
            "digests": row["digests"] or 0,
            "last_sent": row["last_sent"],
            "avg_quality": round(row["avg_quality"], 2) if row["avg_quality"] else None,
            "recent_failures": failures["n"] or 0,
            "window_days": days,
        }

    def generate_status_report(self, detailed: bool = False) -> str:
        """Executive summary of agency health, optionally with agent-level detail."""
        stats = self._digest_stats()

        try:
            from utils.metrics_collector import MetricsCollector
            metrics = MetricsCollector()
            agent_perf = metrics.get_agent_performance()
            api_health = metrics.get_api_health()
        except Exception:
            agent_perf, api_health = None, None

        context = f"Digest stats (last {stats['window_days']} days): {stats}\n"
        if detailed and agent_perf:
            context += f"Agent performance: {agent_perf}\n"
        if detailed and api_health:
            context += f"API health: {api_health}\n"

        prompt = f"""Board member has requested a status report. {"Give a DETAILED breakdown." if detailed else "Give a BRIEF executive summary (4-6 sentences)."}

Data:
{context}
"""
        response = self.call_llm(prompt, system_prompt=CEO_SYSTEM_PROMPT, max_tokens=600, json_mode=False)
        if response:
            self.logger.log_action("generate_status_report", output_data={"detailed": detailed}, success=True)
            return response

        # Template fallback if all LLMs are down
        return self._template_status_report(stats, detailed)

    def _template_status_report(self, stats: Dict, detailed: bool) -> str:
        lines = [
            "ALEX (CEO Agent) — Status Report [template mode: LLM unavailable]",
            f"- Digests sent (last {stats['window_days']}d): {stats['digests']}",
            f"- Stories delivered: {stats['total_sent']}",
            f"- Last digest: {stats['last_sent'] or 'never'}",
            f"- Avg quality score: {stats['avg_quality'] if stats['avg_quality'] is not None else 'n/a'}",
            f"- Failures logged: {stats['recent_failures']}",
        ]
        if stats["recent_failures"] > 0:
            lines.append("⚠️  Recommend reviewing agent_logs for root cause.")
        return "\n".join(lines)

    def handle_query(self, question: str) -> str:
        """Free-form board question, answered with grounded operational context."""
        stats = self._digest_stats()
        prompt = f"""Board member asks: "{question}"

Current operational data: {stats}

Answer directly and concisely, grounded in this data. If the question can't be answered from this data, say so.
"""
        response = self.call_llm(prompt, system_prompt=CEO_SYSTEM_PROMPT, max_tokens=500, json_mode=False)
        self.logger.log_action("handle_query", input_data={"question": question}, success=response is not None)
        return response or "I'm currently unable to reach my reasoning engines (Claude and Groq both failed). Please retry shortly."

    def switch_digest_mode(self, mode: str) -> bool:
        """Task 5.3: actually flips the persisted digest mode (daily <-> weekly)."""
        ok = mode_state.set_mode(mode)
        self.logger.log_action("switch_digest_mode", input_data={"mode": mode}, success=ok)
        if ok:
            print(f"🔀 ALEX: digest mode switched to '{mode}'")
        return ok

    def handle_strategic_command(self, command: str) -> str:
        """
        Handle board-issued strategic commands (e.g. 'pause', 'switch to weekly mode',
        'raise quality bar'). Mode-switch commands actually flip mode_state; anything
        else is logged and acknowledged for manual/automated follow-up.
        """
        self.logger.log_action("handle_strategic_command", input_data={"command": command}, success=True)

        lower = command.lower()
        mode_switched = None
        if "weekly" in lower:
            self.switch_digest_mode(mode_state.WEEKLY)
            mode_switched = mode_state.WEEKLY
        elif "daily" in lower:
            self.switch_digest_mode(mode_state.DAILY)
            mode_switched = mode_state.DAILY

        prompt = f"""Board member issued this strategic command: "{command}"
{"The digest mode has been switched to " + mode_switched + "." if mode_switched else ""}

Acknowledge the command, restate what it means operationally in one or two sentences, \
and note that it has been logged for execution.
"""
        response = self.call_llm(prompt, system_prompt=CEO_SYSTEM_PROMPT, max_tokens=300, json_mode=False)
        if response:
            return response
        if mode_switched:
            return f"Digest mode switched to '{mode_switched}'. Command logged: \"{command}\"."
        return f"Command received and logged: \"{command}\". (LLM unavailable — manual follow-up required.)"

    def escalate_to_board(self, severity: str, summary: str, details: Optional[Dict] = None) -> Dict:
        """Record a critical/error-level escalation for board visibility (Task 3.4 hook)."""
        escalation = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": severity,
            "summary": summary,
            "details": details or {},
        }
        self.escalations.append(escalation)
        self.logger.log_action("escalate_to_board", input_data=escalation, success=True, level="ERROR")
        print(f"🚨 CEO ESCALATION [{severity}]: {summary}")
        return escalation

    def handle_message(self, message: Dict) -> Dict:
        """Message-router entrypoint for CEO commands from other agents (e.g. escalations)."""
        payload = message.get("payload", {})
        mtype = message["type"]
        if mtype == "escalate":
            return self.escalate_to_board(payload.get("severity", "ERROR"), payload.get("summary", ""), payload.get("details"))
        if mtype == "status":
            return {"report": self.generate_status_report(payload.get("detailed", False))}
        if mtype == "query":
            return {"answer": self.handle_query(payload.get("question", ""))}
        if mtype == "report":
            # Informational report from another agent (e.g. Scout's weekly run) - log & acknowledge.
            self.logger.log_action("receive_report", input_data=payload, success=True)
            print(f"📥 ALEX received report — {payload.get('title', 'Untitled')}: {payload.get('summary', '')}")
            return {"acknowledged": True}
        return {"error": f"unknown message type {mtype}"}


ceo_agent = CEOAgent()
register_agent("ceo", ceo_agent.handle_message)
