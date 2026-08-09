"""
API Key Validation & Health Checks

Validates Anthropic and Groq API keys on startup.
Detects placeholder/invalid keys and provides clear error messages.
Implements fallback strategy: proceed with available keys or fail fast.
"""
import os
from typing import Tuple, Optional


def validate_anthropic_key() -> Tuple[bool, Optional[str]]:
    """
    Validate Anthropic API key.
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
        - (True, None) if key is valid
        - (False, error_message) if key is invalid or test fails
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    
    # Check if key exists
    if not api_key:
        return False, "ANTHROPIC_API_KEY environment variable is not set"
    
    # Check for placeholder keys
    placeholder_patterns = [
        "sk_ant_YOUR_ACTUAL_KEY_HERE",
        "your_key_here",
        "placeholder",
        "xxx",
    ]
    
    if any(pattern.lower() in api_key.lower() for pattern in placeholder_patterns):
        return False, f"Anthropic API key appears to be a placeholder: {api_key[:20]}..."
    
    # Check key format (Anthropic keys start with sk-ant-)
    if not api_key.startswith("sk-ant-"):
        return False, f"Anthropic API key has invalid format (should start with 'sk-ant-')"
    
    # Make test API call
    try:
        import anthropic
        
        client = anthropic.Anthropic(api_key=api_key)
        # Minimal test call with very low token count
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}]
        )
        
        # If we got here, the key works
        return True, None
        
    except anthropic.AuthenticationError as e:
        return False, f"Anthropic API authentication failed: {str(e)}"
    except anthropic.PermissionDeniedError as e:
        return False, f"Anthropic API permission denied: {str(e)}"
    except anthropic.RateLimitError as e:
        # Rate limit means the key is valid but temporarily unavailable
        return True, f"Warning: Anthropic API rate limited (key is valid): {str(e)}"
    except Exception as e:
        return False, f"Anthropic API test failed: {str(e)}"


def validate_groq_key() -> Tuple[bool, Optional[str]]:
    """
    Validate Groq API key.
    
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
        - (True, None) if key is valid
        - (False, error_message) if key is invalid or test fails
    """
    api_key = os.getenv("GROQ_API_KEY")
    
    # Check if key exists
    if not api_key:
        return False, "GROQ_API_KEY environment variable is not set"
    
    # Check for placeholder keys
    placeholder_patterns = [
        "your_key_here",
        "placeholder",
        "xxx",
    ]
    
    if any(pattern.lower() in api_key.lower() for pattern in placeholder_patterns):
        return False, f"Groq API key appears to be a placeholder: {api_key[:20]}..."
    
    # Check key format (Groq keys start with gsk_)
    if not api_key.startswith("gsk_"):
        return False, f"Groq API key has invalid format (should start with 'gsk_')"
    
    # Make test API call
    try:
        from groq import Groq
        
        client = Groq(api_key=api_key)
        # Minimal test call with very low token count
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=10
        )
        
        # If we got here, the key works
        return True, None
        
    except Exception as e:
        error_str = str(e).lower()
        
        # Check for authentication errors
        if "authentication" in error_str or "api key" in error_str or "401" in error_str:
            return False, f"Groq API authentication failed: {str(e)}"
        
        # Check for rate limit (means key is valid but temporarily unavailable)
        if "rate limit" in error_str or "429" in error_str:
            return True, f"Warning: Groq API rate limited (key is valid): {str(e)}"
        
        # Other errors
        return False, f"Groq API test failed: {str(e)}"


def validate_api_keys_on_startup() -> dict:
    """
    Validate all API keys on startup and provide clear feedback.
    
    Returns:
        dict: Validation results with status for each provider
        {
            "anthropic": {"valid": bool, "error": str or None},
            "groq": {"valid": bool, "error": str or None},
            "has_valid_key": bool,
            "can_proceed": bool
        }
    
    Raises:
        RuntimeError: If no valid API keys are available
    """
    print("\n" + "="*70)
    print("🔐 API KEY VALIDATION")
    print("="*70)
    
    results = {
        "anthropic": {"valid": False, "error": None},
        "groq": {"valid": False, "error": None},
        "has_valid_key": False,
        "can_proceed": False
    }
    
    # Validate Anthropic
    print("\n[1/2] Validating Anthropic (Claude) API key...")
    anthropic_valid, anthropic_error = validate_anthropic_key()
    results["anthropic"]["valid"] = anthropic_valid
    results["anthropic"]["error"] = anthropic_error
    
    if anthropic_valid:
        print("  ✅ Anthropic API key is VALID")
    else:
        print(f"  ❌ Anthropic API key FAILED: {anthropic_error}")
    
    # Validate Groq
    print("\n[2/2] Validating Groq API key...")
    groq_valid, groq_error = validate_groq_key()
    results["groq"]["valid"] = groq_valid
    results["groq"]["error"] = groq_error
    
    if groq_valid:
        print("  ✅ Groq API key is VALID")
    else:
        print(f"  ❌ Groq API key FAILED: {groq_error}")
    
    # Determine if we can proceed
    print("\n" + "-"*70)
    print("📊 VALIDATION SUMMARY")
    print("-"*70)
    
    results["has_valid_key"] = anthropic_valid or groq_valid
    
    if anthropic_valid and groq_valid:
        print("✅ Both API keys are valid")
        print("   Primary: Claude (Anthropic)")
        print("   Fallback: Groq")
        results["can_proceed"] = True
        
    elif anthropic_valid and not groq_valid:
        print("⚠️  Only Claude (Anthropic) API key is valid")
        print("   System will use Claude only (no Groq fallback)")
        print(f"   Groq error: {groq_error}")
        results["can_proceed"] = True
        
    elif groq_valid and not anthropic_valid:
        print("⚠️  Only Groq API key is valid")
        print("   System will use Groq only (no Claude fallback)")
        print(f"   Claude error: {anthropic_error}")
        results["can_proceed"] = True
        
    else:
        print("❌ NO VALID API KEYS AVAILABLE")
        print("\nErrors:")
        print(f"  • Claude: {anthropic_error}")
        print(f"  • Groq: {groq_error}")
        print("\nPlease fix your API keys in the .env file and try again.")
        results["can_proceed"] = False
        
        raise RuntimeError(
            "No valid API keys available. Cannot proceed without at least one working LLM provider."
        )
    
    print("="*70 + "\n")
    
    return results


# Fallback Strategy Documentation
FALLBACK_STRATEGY = """
API Key Fallback Strategy
=========================

The system requires at least ONE valid API key to operate:
- Anthropic (Claude) - Primary provider for high-quality outputs
- Groq - Secondary provider for speed and reliability

Fallback Behavior:
1. If BOTH keys valid: Use Claude with Groq as fallback
2. If ONLY Claude valid: Use Claude exclusively (no fallback)
3. If ONLY Groq valid: Use Groq exclusively (no fallback)
4. If NO keys valid: FAIL FAST with clear error message

Key Validation Checks:
- Environment variable exists
- Not a placeholder (e.g., "sk_ant_YOUR_ACTUAL_KEY_HERE")
- Correct format (Claude: sk-ant-*, Groq: gsk_*)
- Test API call succeeds (authentication works)

To fix invalid keys:
1. Edit .env file
2. Set valid API keys:
   ANTHROPIC_API_KEY=sk-ant-your_actual_key
   GROQ_API_KEY=gsk_your_actual_key
3. Restart the pipeline

For API key setup:
- Claude: https://console.anthropic.com/
- Groq: https://console.groq.com/
"""
