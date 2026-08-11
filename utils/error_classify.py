"""
Shared LLM-error classification.

Turns a raw provider exception string into (a) a stable, human-readable reason for
the dashboard's Processing History panel, and (b) a quota/rate-limit flag the
circuit breaker uses to pick a cooldown (utils/error_handling.py). Deliberately
provider-agnostic - it doesn't guess "this must be Groq" from message wording;
callers that know the provider (agent_logs.action is "call_llm[groq]" etc.,
base_agent.py knows which block it's in) attach that themselves.
"""
import re


def classify_error(msg: str) -> str:
    """Collapse a raw exception string into a short, stable reason so near-identical
    errors (e.g. 100 Groq 429s with different token counts) group into one line
    instead of 100."""
    if not msg:
        return "unknown error"
    m = msg.lower()
    if "tokens per day" in m or "tpd" in m or ("quota" in m and "exceeded" in m):
        return "daily quota exceeded"
    if "rate_limit" in m or "rate limit" in m or "429" in m:
        return "rate limited"
    if "invalid x-api-key" in m or "authentication_error" in m or "401" in m or "api key not valid" in m:
        return "API key invalid/expired"
    if "circuit open" in m or "all llm providers failed" in m:
        return "all providers exhausted (circuit breaker open)"
    if "timeout" in m or "deadline" in m:
        return "request timeout"
    return msg[:100]


def is_quota_error(msg: str) -> bool:
    """True for errors that mean 'this provider is out of budget for a while' (daily
    quota, rate limit) as opposed to a one-off network blip. These get a much longer
    circuit-breaker cooldown so a fresh process doesn't waste real calls
    rediscovering the same outage every 15 minutes (see CircuitBreaker)."""
    if not msg:
        return False
    m = msg.lower()
    return any(k in m for k in ("tokens per day", "tpd", "rate_limit", "rate limit", "429", "quota"))


# Matches the provider's own stated wait time, so the circuit breaker can trust it
# instead of guessing. Both providers in this codebase put it right in the message:
#   Groq:   "Please try again in 46m13.43s"  /  "in 42s"
#   Gemini: "retryDelay': '41s'"  /  "Please retry in 41.9s"
_RETRY_PATTERNS = [
    re.compile(r"try again in (?:(\d+)m)?(\d+(?:\.\d+)?)s", re.IGNORECASE),
    re.compile(r"retry in (\d+(?:\.\d+)?)s", re.IGNORECASE),
    re.compile(r"retrydelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", re.IGNORECASE),
]


def extract_retry_seconds(msg: str) -> "int | None":
    """Pull the provider's own suggested wait time out of the error text, if it gave
    one. Distinguishes "this specific limit clears in 42 seconds" (Gemini's 5-req/min
    free-tier cap) from "this needs the daily quota to roll over" (Groq's tokens-per-
    day cap resetting in 46 minutes) - is_quota_error() alone can't tell those apart,
    it only knows "some kind of quota/rate limit," which is how a 42-second blip was
    getting the same blanket 6-hour cooldown as an actual multi-hour daily exhaustion.
    Returns None (caller falls back to the fixed cooldown) if nothing parses."""
    if not msg:
        return None
    for pattern in _RETRY_PATTERNS:
        match = pattern.search(msg)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 2:  # "Xm Ys" form
            minutes = float(groups[0]) if groups[0] else 0.0
            seconds = float(groups[1])
            return int(minutes * 60 + seconds)
        return int(float(groups[0]))
    return None
