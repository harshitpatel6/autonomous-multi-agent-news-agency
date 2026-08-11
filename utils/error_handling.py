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
    failures, stays open for `cooldown_seconds` (or `quota_cooldown_seconds` when the
    failure was a quota/rate-limit error, see record_failure(quota_exceeded=)), then
    allows one trial call (half-open) before fully closing again on success.

    State is wall-clock (time.time(), not time.monotonic()) and persisted to the
    `provider_state` DB table. publish.py runs as a brand-new process every 15
    minutes via launchd, so an in-memory-only breaker forgets "Groq is quota-
    exhausted" the instant that process exits - every subsequent run would burn
    through `failure_threshold` real failed calls rediscovering the same outage
    before it even opens. Persisting lets a fresh process skip a still-cooling-down
    provider immediately instead of re-probing it.
    """

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: int = 60,
                 quota_cooldown_seconds: int = 6 * 3600):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.quota_cooldown_seconds = quota_cooldown_seconds
        self._failures: Dict[str, int] = {}
        self._opened_at: Dict[str, float] = {}
        self._cooldown_for: Dict[str, int] = {}
        self._loaded = False

    def _ensure_loaded(self):
        """Lazily pull persisted open/cooldown state from the DB on first use per
        process. Best-effort: if the DB isn't available (standalone scripts, tests
        that don't init_db()), the breaker just behaves as pure in-memory."""
        if self._loaded:
            return
        self._loaded = True
        try:
            from db import get_connection
            conn = get_connection()
            rows = conn.execute("SELECT service, opened_at, cooldown_seconds FROM provider_state").fetchall()
            conn.close()
            for r in rows:
                self._opened_at[r["service"]] = r["opened_at"]
                self._cooldown_for[r["service"]] = r["cooldown_seconds"]
                self._failures[r["service"]] = self.failure_threshold
        except Exception:
            pass

    def _persist(self, service: str):
        try:
            from db import get_connection
            conn = get_connection()
            if service in self._opened_at:
                conn.execute(
                    """INSERT INTO provider_state (service, opened_at, cooldown_seconds) VALUES (?, ?, ?)
                       ON CONFLICT(service) DO UPDATE SET
                           opened_at = excluded.opened_at, cooldown_seconds = excluded.cooldown_seconds""",
                    (service, self._opened_at[service], self._cooldown_for.get(service, self.cooldown_seconds)),
                )
            else:
                conn.execute("DELETE FROM provider_state WHERE service = ?", (service,))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def is_open(self, service: str) -> bool:
        self._ensure_loaded()
        opened_at = self._opened_at.get(service)
        if opened_at is None:
            return False
        cooldown = self._cooldown_for.get(service, self.cooldown_seconds)
        if time.time() - opened_at >= cooldown:
            return False  # cooldown elapsed -> half-open, allow a trial call
        return True

    def record_success(self, service: str):
        self._ensure_loaded()
        self._failures[service] = 0
        if service in self._opened_at:
            self._opened_at.pop(service, None)
            self._cooldown_for.pop(service, None)
            self._persist(service)

    def record_failure(self, service: str, quota_exceeded: bool = False, retry_after_seconds: "int | None" = None):
        """`retry_after_seconds` (parsed from the provider's own error message by
        utils.error_classify.extract_retry_seconds) overrides the blanket
        quota_cooldown_seconds when present - trusting "this clears in 42s" instead
        of benching the provider for 6 hours over what's really a per-minute cap.
        Clamped so a bad/adversarial parse can't produce a near-zero hot-loop or an
        absurdly long bench."""
        self._ensure_loaded()
        self._failures[service] = self._failures.get(service, 0) + 1
        if self._failures[service] >= self.failure_threshold:
            self._opened_at[service] = time.time()
            if retry_after_seconds is not None:
                cooldown = max(self.cooldown_seconds, min(retry_after_seconds, self.quota_cooldown_seconds))
            else:
                cooldown = self.quota_cooldown_seconds if quota_exceeded else self.cooldown_seconds
            self._cooldown_for[service] = cooldown
            self._persist(service)

    def status(self) -> Dict[str, Dict]:
        self._ensure_loaded()
        return {
            svc: {"failures": self._failures.get(svc, 0), "open": self.is_open(svc)}
            for svc in set(self._failures) | set(self._opened_at)
        }


# Shared breaker across all agents (Claude/Groq/Gemini call sites)
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
