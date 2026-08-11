"""
Base Agent class: shared LLM calling (Claude -> Groq -> Gemini fallback), logging,
and error-handling primitives used by every specialized agent. (Supports Tasks 2.6,
3.1, 3.4)
"""
import time
import json as _json
from typing import Optional

from config import ANTHROPIC_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, CLAUDE_MODEL, GROQ_MODEL, GEMINI_MODEL
from utils.agent_logger import AgentLogger
from utils.error_handling import breaker, classify_and_escalate, CRITICAL
from utils.error_classify import is_quota_error, extract_retry_seconds

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

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
except ImportError:
    GEMINI_AVAILABLE = False

# All providers this codebase knows how to fall back through, in priority order.
# Used to decide when every option is exhausted (see call_llm's final CRITICAL check)
# without hardcoding a 2-provider assumption in multiple places.
ALL_PROVIDERS = ("claude", "groq", "gemini")

# See the comment at the Gemini call site: padding for GEMINI_MODEL's internal
# "thinking" tokens, which come out of max_output_tokens before the visible answer.
GEMINI_THINKING_TOKEN_BUFFER = 300


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
        self.gemini_client = None
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
        if GEMINI_AVAILABLE:
            try:
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
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
        """Universal LLM caller: Claude -> Groq -> Gemini, retrying the first with
        backoff on transient errors before falling through. Each provider call is
        wrapped by the shared circuit breaker, so a provider that's failing hard
        (esp. a quota/rate-limit error, which gets a multi-hour cooldown instead of
        the default 60s - see CircuitBreaker) gets skipped entirely on the next call
        instead of being re-probed and wasting the request."""
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
                    breaker.record_failure("claude", quota_exceeded=is_quota_error(str(e)), retry_after_seconds=extract_retry_seconds(str(e)))
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
                breaker.record_failure("groq", quota_exceeded=is_quota_error(str(e)), retry_after_seconds=extract_retry_seconds(str(e)))
                self._log_llm_call("groq", False, start, error=str(e))

        if self.gemini_client and not breaker.is_open("gemini"):
            try:
                # GEMINI_MODEL is a "thinking" model - it spends ~150 tokens of its
                # max_output_tokens budget on internal reasoning before the visible
                # answer (confirmed empirically: thoughts_token_count ~136-140 on a
                # trivial prompt), so a tight budget silently returns empty text with
                # finish_reason=MAX_TOKENS rather than an error. Pad the budget so the
                # thinking overhead never starves the actual answer.
                response = self.gemini_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=system_prompt if system_prompt else None,
                        max_output_tokens=max_tokens + GEMINI_THINKING_TOKEN_BUFFER,
                    ),
                )
                text = (response.text or "").strip()
                if json_mode:
                    text = text.replace("```json", "").replace("```", "").strip()
                if not text:
                    raise ValueError("Gemini returned empty text (likely hit max_output_tokens or was filtered)")
                self._log_llm_call("gemini", True, start)
                breaker.record_success("gemini")
                return text
            except Exception as e:
                breaker.record_failure("gemini", quota_exceeded=is_quota_error(str(e)), retry_after_seconds=extract_retry_seconds(str(e)))
                self._log_llm_call("gemini", False, start, error=str(e))

        self.logger.log_action(
            "call_llm", input_data={"prompt_preview": prompt[:200]}, success=False,
            error_message="All LLM providers failed or circuit open", level="ERROR",
        )
        if all(breaker.is_open(p) for p in ALL_PROVIDERS):
            classify_and_escalate(
                self.name, RuntimeError("Claude, Groq, and Gemini circuits all open"), CRITICAL,
                context="All LLM providers are failing repeatedly — consider degraded mode",
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
