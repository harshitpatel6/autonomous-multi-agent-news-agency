"""
Base Agent class: shared LLM calling (Claude -> Groq fallback), logging, and
error-handling primitives used by every specialized agent. (Supports Tasks 2.6, 3.1, 3.4)
"""
import time
import json as _json
from typing import Optional

from config import ANTHROPIC_API_KEY, GROQ_API_KEY, CLAUDE_MODEL, GROQ_MODEL
from utils.agent_logger import AgentLogger
from utils.error_handling import breaker, classify_and_escalate, CRITICAL

try:
    import anthropic
    CLAUDE_AVAILABLE = bool(ANTHROPIC_API_KEY and "YOUR_ACTUAL_KEY" not in (ANTHROPIC_API_KEY or ""))
except ImportError:
    CLAUDE_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = bool(GROQ_API_KEY)
except ImportError:
    GROQ_AVAILABLE = False


class AgentError(Exception):
    """Raised for agent-level failures. severity: INFO/WARNING/ERROR/CRITICAL."""
    def __init__(self, message: str, severity: str = "ERROR"):
        super().__init__(message)
        self.severity = severity


class Agent:
    """Base class for all specialized agents. Provides resilient LLM access + logging."""

    def __init__(self, name: str):
        self.name = name
        self.logger = AgentLogger(name)

        self.claude_client = None
        self.groq_client = None
        if CLAUDE_AVAILABLE:
            try:
                self.claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            except Exception:
                pass
        if GROQ_AVAILABLE:
            try:
                self.groq_client = Groq(api_key=GROQ_API_KEY)
            except Exception:
                pass

    def call_llm(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1000,
        json_mode: bool = True,
        retries: int = 2,
    ) -> Optional[str]:
        """Universal LLM caller: Claude primary, Groq fallback, retry with backoff on transient errors."""
        start = time.monotonic()

        if self.claude_client and not breaker.is_open("claude"):
            for attempt in range(retries + 1):
                try:
                    response = self.claude_client.messages.create(
                        model=CLAUDE_MODEL,
                        max_tokens=max_tokens,
                        system=system_prompt if system_prompt else None,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = response.content[0].text.strip()
                    if json_mode:
                        text = text.replace("```json", "").replace("```", "").strip()
                    self._log_llm_call("claude", True, start)
                    breaker.record_success("claude")
                    return text
                except Exception as e:
                    transient = self._is_transient(e)
                    if transient and attempt < retries:
                        time.sleep(2 ** attempt)
                        continue
                    breaker.record_failure("claude")
                    self._log_llm_call("claude", False, start, error=str(e))
                    break

        if self.groq_client and not breaker.is_open("groq"):
            try:
                messages = [{"role": "user", "content": prompt}]
                if system_prompt:
                    messages.insert(0, {"role": "system", "content": system_prompt})
                response = self.groq_client.chat.completions.create(
                    model=GROQ_MODEL, max_tokens=max_tokens, messages=messages, timeout=30
                )
                text = response.choices[0].message.content.strip()
                if json_mode:
                    text = text.replace("```json", "").replace("```", "").strip()
                self._log_llm_call("groq", True, start)
                breaker.record_success("groq")
                return text
            except Exception as e:
                breaker.record_failure("groq")
                self._log_llm_call("groq", False, start, error=str(e))

        self.logger.log_action(
            "call_llm", input_data={"prompt_preview": prompt[:200]}, success=False,
            error_message="All LLM providers failed or circuit open", level="ERROR",
        )
        if breaker.is_open("claude") and breaker.is_open("groq"):
            classify_and_escalate(
                self.name, RuntimeError("Both Claude and Groq circuits open"), CRITICAL,
                context="Both LLM providers are failing repeatedly — consider degraded mode",
            )
        return None

    def _log_llm_call(self, provider, success, start, error=None):
        elapsed_ms = int((time.monotonic() - start) * 1000)
        self.logger.log_action(
            f"call_llm[{provider}]", success=success, error_message=error,
            execution_time_ms=elapsed_ms, level="DEBUG" if success else "WARNING",
        )

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(k in msg for k in ("timeout", "rate", "429", "503", "overloaded", "connection"))

    @staticmethod
    def parse_json(text: Optional[str], default=None):
        if not text:
            return default
        try:
            return _json.loads(text)
        except Exception:
            return default
