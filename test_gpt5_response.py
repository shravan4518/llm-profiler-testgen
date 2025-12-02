"""Test if GPT-5 is responding with content"""
import sys
from pathlib import Path
import io

# Fix Windows console encoding for Unicode
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import config
from openai import AzureOpenAI

print("=" * 80)
print("TESTING GPT-5.1-2 RESPONSE")
print("=" * 80)

client = AzureOpenAI(
    azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
    api_key=config.AZURE_OPENAI_API_KEY,
    api_version=config.AZURE_OPENAI_API_VERSION
)

# Test 1: Simple prompt
print("\nTest 1: Simple prompt")
print("-" * 80)
response1 = client.chat.completions.create(
    model="gpt-5.1-2",
    messages=[{"role": "user", "content": "Say hello"}],
    temperature=1.0,
    max_completion_tokens=100
)
print(f"Response: {response1.choices[0].message.content}")
print(f"Length: {len(response1.choices[0].message.content or '')}")
print(f"Finish reason: {response1.choices[0].finish_reason}")

# Test 2: Test case generation prompt
print("\nTest 2: Test case generation")
print("-" * 80)
response2 = client.chat.completions.create(
    model="gpt-5.1-2",
    messages=[
        {"role": "system", "content": "You are a test case expert."},
        {"role": "user", "content": "Generate 3 test cases for database upgrade functionality"}
    ],
    temperature=1.0,
    max_completion_tokens=2000
)
print(f"Response length: {len(response2.choices[0].message.content or '')}")
print(f"First 500 chars: {response2.choices[0].message.content[:500]}")
print(f"Finish reason: {response2.choices[0].finish_reason}")

# Test 3: Long system prompt (like our actual system)
print("\nTest 3: Long system prompt")
print("-" * 80)
long_system = """You are an elite QA Test Architect and Test Case Designer with 20+ years of experience in enterprise software testing.

You are an expert in:
- IEEE 829 and ISO/IEC/IEEE 29119 testing standards
- Comprehensive test coverage analysis
- Test case design for maximum defect detection

Your test cases are known for being:
- Exhaustively comprehensive
- Precisely detailed
- Properly categorized"""

response3 = client.chat.completions.create(
    model="gpt-5.1-2",
    messages=[
        {"role": "system", "content": long_system},
        {"role": "user", "content": "Generate test cases for profiler database upgrade"}
    ],
    temperature=1.0,
    max_completion_tokens=16000  # Increased from 2000 to allow full response
)
print(f"Response length: {len(response3.choices[0].message.content or '')}")
print(f"Content is None: {response3.choices[0].message.content is None}")
print(f"Content is empty string: {response3.choices[0].message.content == ''}")
if response3.choices[0].message.content:
    print(f"First 300 chars: {response3.choices[0].message.content[:300]}")
print(f"Finish reason: {response3.choices[0].finish_reason}")

print("\n" + "=" * 80)
print("TESTS COMPLETE")
print("=" * 80)
