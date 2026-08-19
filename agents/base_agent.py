"""
Base Agent class: shared LLM calling (Gemini), logging, and error-handling
primitives used by every specialized agent. (Supports Tasks 2.6, 3.1, 3.4)

Gemini is the only provider call_llm() uses. This used to fall through
Claude -> Groq -> Gemini, but Claude's key in .env was a placeholder that was
never replaced (Claude was never actually called, in the project's entire
history - see git history on CLAUDE_AVAILABLE if you need the forensics), and
Groq's free-tier daily quota (100k tokens/day) got exhausted most runs anyway,
which just added log noise and startup latency for a provider that wasn't
carrying real traffic. Simplified to call the one provider that's actually
paid/configured and has been carrying ~100% of real traffic already. See
CLAUDE_AVAILABLE / GROQ_AVAILABLE below if either provider gets a real,
working key again later - they're kept as informational flags (imported by
agent_coordinator.py / orchestration_graph.py's degraded-mode checks) but
call_llm() itself no longer attempts either.
"""
import time
import json as _json
from typing import Optional

from config import GEMINI_API_KEY, GEMINI_MODEL
from utils.agent_logger import AgentLogger
from utils.error_handling import breaker, classify_and_escalate, CRITICAL
from utils.error_classify import is_quota_error, extract_retry_seconds

# Fixed off: call_llm() no longer attempts either provider (see module docstring).
# Kept as named constants rather than deleted so agent_coordinator.py's and
# orchestration_graph.py's "is any LLM available at all" degraded-mode checks
# don't need an unrelated rewrite - they already OR this in with GEMINI_AVAILABLE.
CLAUDE_AVAILABLE = False
GROQ_AVAILABLE = False

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
except ImportError:
    GEMINI_AVAILABLE = False

# Used by summarize.py's _infer_failure_reason to tell "the provider is rate-limited"
# apart from "the model returned garbage for this specific cluster" - kept as a tuple
# (rather than inlining "gemini" there) so that file doesn't hardcode a provider name.
ALL_PROVIDERS = ("gemini",)

# See the comment at the Gemini call site: padding for GEMINI_MODEL's internal
# "thinking" tokens, which come out of max_output_tokens before the visible answer.
# 300 was sized off a trivial prompt (thoughts_token_count ~136-140). Real reporter
# prompts (legal rule + beat instructions + 4-part task) measured ~960 thinking
# tokens with thinking capped at "low" measured ~470 - so 300 silently truncated
# every real call. Paired with thinking_level="low" at the call site below, which
# keeps thinking bounded instead of scaling with prompt complexity.
GEMINI_THINKING_TOKEN_BUFFER = 800


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

        self.gemini_client = None
        if GEMINI_AVAILABLE:
            try:
                self.gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            except Exception as e:
                # A client that fails to construct here used to fail silently (bare
                # except: pass) - the only way anyone found out Claude's key was a
                # placeholder was by cross-referencing agent_logs by hand. Logging
                # through the same AgentLogger call_llm[...] uses means a bad key
                # shows up in agent_logs / the dashboard's error summary on the very
                # first run instead of just never being called, with no trace either way.
                self.logger.log_action("init_client[gemini]", success=False, error_message=str(e), level="WARNING")

    def call_llm(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1000,
        json_mode: bool = True,
        retries: int = 2,
    ) -> Optional[str]:
        """Gemini caller with retry + backoff on transient errors. Wrapped by the shared
        circuit breaker, so a hard failure (esp. a quota/rate-limit error, which gets a
        multi-hour cooldown instead of the default 60s - see CircuitBreaker) gets skipped
        entirely on the next call instead of being re-probed and wasting the request."""
        start = time.monotonic()

        if self.gemini_client and not breaker.is_open("gemini"):
            for attempt in range(retries + 1):
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
                            thinking_config=genai_types.ThinkingConfig(thinking_level="low"),
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
                    transient = self._is_transient(e)
                    if transient and attempt < retries:
                        time.sleep(2 ** attempt)
                        continue
                    breaker.record_failure("gemini", quota_exceeded=is_quota_error(str(e)), retry_after_seconds=extract_retry_seconds(str(e)))
                    self._log_llm_call("gemini", False, start, error=str(e))
                    break

        self.logger.log_action(
            "call_llm", input_data={"prompt_preview": prompt[:200]}, success=False,
            error_message="Gemini failed or circuit open", level="ERROR",
        )
        if breaker.is_open("gemini"):
            classify_and_escalate(
                self.name, RuntimeError("Gemini circuit open"), CRITICAL,
                context="Gemini (the only configured LLM provider) is failing repeatedly — consider degraded mode",
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
