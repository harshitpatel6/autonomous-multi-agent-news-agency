#!/usr/bin/env python
"""
Manual integration test for API key validation on startup
Run this to test the validation system without running the full pipeline
"""
from dotenv import load_dotenv
load_dotenv()

from utils.api_validator import validate_api_keys_on_startup


if __name__ == "__main__":
    print("Testing API key validation on startup...\n")
    
    try:
        results = validate_api_keys_on_startup()
        
        print("\n✅ VALIDATION SUCCEEDED")
        print(f"   Can proceed: {results['can_proceed']}")
        print(f"   Anthropic valid: {results['anthropic']['valid']}")
        print(f"   Groq valid: {results['groq']['valid']}")
        
    except RuntimeError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        exit(1)
