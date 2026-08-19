"""
API Key Validation & Health Checks

Validates the Gemini API key on startup - Gemini is the only LLM provider the
pipeline actually calls (see agents/base_agent.py: ALL_PROVIDERS = ("gemini",)).
Anthropic and Groq are checked too, but purely informationally: this codebase used
to fall back between Claude/Groq/Gemini, but every LLM call today goes through
agents/base_agent.py's Gemini-only client. An invalid/placeholder Anthropic or Groq
key is expected and harmless - it must never block startup. (It used to: this
gate raised RuntimeError whenever Anthropic AND Groq were both invalid, even when
Gemini - the key actually paying for and running every request - was perfectly
valid. That silently aborted the whole pipeline, before it ingested a single feed,
on any night either of those two unused keys happened to fail their live test call.)
"""
import os
from typing import Tuple, Optional


def validate_gemini_key() -> Tuple[bool, Optional[str]]:
    """
    Validate the Gemini API key - the provider the pipeline actually uses.

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return False, "GEMINI_API_KEY environment variable is not set"

    placeholder_patterns = ["your_key_here", "placeholder", "xxx", "YOUR_ACTUAL_KEY"]
    if any(pattern.lower() in api_key.lower() for pattern in placeholder_patterns):
        return False, f"Gemini API key appears to be a placeholder: {api_key[:12]}..."

    # Make a minimal live test call so a revoked/expired key is caught here with a
    # clear message, instead of surfacing 90 times as "call_llm[gemini] — FAILED"
    # deep in summarize_clusters().
    try:
        from google import genai
        from config import GEMINI_MODEL

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=GEMINI_MODEL, contents="test")

        if not response:
            return False, "Gemini API test call returned no response"
        return True, None

    except Exception as e:
        error_str = str(e).lower()
        if "rate limit" in error_str or "429" in error_str or "quota" in error_str:
            # Valid key, temporarily throttled - still fine to proceed, the pipeline's
            # own circuit breaker (utils/error_handling.py) handles cooldowns per-call.
            return True, f"Warning: Gemini API rate limited (key is valid): {e}"
        if "401" in error_str or "403" in error_str or "authentication" in error_str or "api key" in error_str:
            return False, f"Gemini API authentication failed: {e}"
        return False, f"Gemini API test failed: {e}"


def validate_anthropic_key() -> Tuple[bool, Optional[str]]:
    """Informational only - Anthropic is not called by the pipeline anymore."""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        return False, "ANTHROPIC_API_KEY environment variable is not set"

    placeholder_patterns = ["sk_ant_YOUR_ACTUAL_KEY_HERE", "your_key_here", "placeholder", "xxx"]
    if any(pattern.lower() in api_key.lower() for pattern in placeholder_patterns):
        return False, f"Anthropic API key appears to be a placeholder: {api_key[:20]}..."

    if not api_key.startswith("sk-ant-"):
        return False, "Anthropic API key has invalid format (should start with 'sk-ant-')"

    return True, None


def validate_groq_key() -> Tuple[bool, Optional[str]]:
    """Informational only - Groq is not called by the pipeline anymore."""
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return False, "GROQ_API_KEY environment variable is not set"

    placeholder_patterns = ["your_key_here", "placeholder", "xxx"]
    if any(pattern.lower() in api_key.lower() for pattern in placeholder_patterns):
        return False, f"Groq API key appears to be a placeholder: {api_key[:20]}..."

    if not api_key.startswith("gsk_"):
        return False, "Groq API key has invalid format (should start with 'gsk_')"

    return True, None


def validate_api_keys_on_startup() -> dict:
    """
    Validate API keys on startup. Gemini is required - it's the only provider the
    pipeline calls. Anthropic/Groq are reported for visibility only and never block
    a run.

    Returns:
        dict: {"gemini": {...}, "anthropic": {...}, "groq": {...}, "can_proceed": bool}

    Raises:
        RuntimeError: only if Gemini itself is missing/invalid.
    """
    print("\n" + "=" * 70)
    print("🔐 API KEY VALIDATION")
    print("=" * 70)

    results = {
        "gemini": {"valid": False, "error": None},
        "anthropic": {"valid": False, "error": None},
        "groq": {"valid": False, "error": None},
        "can_proceed": False,
    }

    print("\n[1/3] Validating Gemini API key (required - the only provider in use)...")
    gemini_valid, gemini_error = validate_gemini_key()
    results["gemini"] = {"valid": gemini_valid, "error": gemini_error}
    print(f"  ✅ Gemini API key is VALID" if gemini_valid else f"  ❌ Gemini API key FAILED: {gemini_error}")

    print("\n[2/3] Checking Anthropic key (informational - not used by the pipeline)...")
    anthropic_valid, anthropic_error = validate_anthropic_key()
    results["anthropic"] = {"valid": anthropic_valid, "error": anthropic_error}
    print(f"  ✅ present" if anthropic_valid else f"  ⚪ {anthropic_error} (fine - unused)")

    print("\n[3/3] Checking Groq key (informational - not used by the pipeline)...")
    groq_valid, groq_error = validate_groq_key()
    results["groq"] = {"valid": groq_valid, "error": groq_error}
    print(f"  ✅ present" if groq_valid else f"  ⚪ {groq_error} (fine - unused)")

    print("\n" + "-" * 70)
    print("📊 VALIDATION SUMMARY")
    print("-" * 70)

    if gemini_valid:
        print("✅ Gemini API key is valid - pipeline can proceed")
        results["can_proceed"] = True
    else:
        print("❌ GEMINI API KEY INVALID - cannot proceed")
        print(f"   {gemini_error}")
        print("\nPlease fix GEMINI_API_KEY in the .env file and try again.")
        results["can_proceed"] = False
        raise RuntimeError(f"Gemini API key is invalid: {gemini_error}")

    print("=" * 70 + "\n")
    return results


# Fallback Strategy Documentation
FALLBACK_STRATEGY = """
API Key Strategy
=================

Gemini is the sole LLM provider the pipeline calls (agents/base_agent.py). A valid
GEMINI_API_KEY is required to proceed; Anthropic/Groq keys are checked for
visibility only and are never a reason to block a run.

To fix an invalid Gemini key:
1. Edit .env
2. Set GEMINI_API_KEY=<your actual key>
3. Restart the pipeline

Gemini key setup: https://aistudio.google.com/apikey
"""
