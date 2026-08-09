#!/usr/bin/env python
"""
Test that main.py properly integrates API validation
This simulates the startup portion only
"""
import sys
from dotenv import load_dotenv
load_dotenv()

# Mock the pipeline functions to prevent actual execution
class MockModule:
    def __getattr__(self, name):
        def mock_func(*args, **kwargs):
            print(f"  [MOCK] Would call {name}()")
            if name == 'build_digest_html':
                return ("<html>mock</html>", [1, 2, 3])
            return None
        return mock_func

sys.modules['db'] = MockModule()
sys.modules['ingest'] = MockModule()
sys.modules['dedup'] = MockModule()
sys.modules['summarize'] = MockModule()
sys.modules['digest'] = MockModule()
sys.modules['send_email'] = MockModule()

# Now import and test main
from main import run

print("Testing main.py integration with API validation...\n")
run()
print("\n✅ Integration test complete!")
