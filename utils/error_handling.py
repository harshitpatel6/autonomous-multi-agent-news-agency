"""
Error Handling & Recovery (Task 3.4): severity levels, circuit breaker for flaky
APIs, and CEO escalation for critical failures. Retry-with-backoff itself lives in
agents/base_agent.py:Agent.call_llm; this module supplies the circuit breaker and
severity-based escalation policy it (and other agents) call into.
"""
import time
from datetime import datetime, timezone
from typing import Dict

INFO, WARNING, ERROR, CRITICAL = "INFO", "WARNING", "ERROR", "CRITICAL"


class CircuitBreaker:
    """
    Per-service circuit breaker: opens after `failure_threshold` consecutive
    failures, stays open for `cooldown_seconds`, then allows one trial call
    (half-open) before fully closing again on success.
    """

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures: Dict[str, int] = {}
        self._opened_at: Dict[str, float] = {}

    def is_open(self, service: str) -> bool:
        opened_at = self._opened_at.get(service)
        if opened_at is None:
            return False
        if time.monotonic() - opened_at >= self.cooldown_seconds:
            return False  # cooldown elapsed -> half-open, allow a trial call
        return True

    def record_success(self, service: str):
        self._failures[service] = 0
        self._opened_at.pop(service, None)

    def record_failure(self, service: str):
        self._failures[service] = self._failures.get(service, 0) + 1
        if self._failures[service] >= self.failure_threshold:
            self._opened_at[service] = time.monotonic()

    def status(self) -> Dict[str, Dict]:
        return {
            svc: {"failures": self._failures.get(svc, 0), "open": self.is_open(svc)}
            for svc in set(self._failures) | set(self._opened_at)
        }


# Shared breaker across all agents (Claude/Groq call sites)
breaker = CircuitBreaker()


def classify_and_escalate(agent_name: str, error: Exception, severity: str = ERROR, context: str = ""):
    """
    Central error policy:
    - INFO/WARNING: log only (handled by caller's AgentLogger)
    - ERROR: log + counted toward circuit breaker
    - CRITICAL: log + immediate CEO escalation
    """
    if severity == CRITICAL:
        try:
            from agents.ceo_agent import ceo_agent
            ceo_agent.escalate_to_board(
                CRITICAL,
                f"{agent_name} hit a critical error: {context or str(error)}",
                details={"error": str(error), "timestamp": datetime.now(timezone.utc).isoformat()},
            )
        except Exception:
            print(f"🚨 CRITICAL in {agent_name} (CEO escalation unavailable): {error}")
