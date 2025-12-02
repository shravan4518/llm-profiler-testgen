"""
Compare GPT-4.1-nano and GPT-5.1-2 test case generation
Shows both models working with easy switching capability
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import config
from src.simple_testgen import SimpleTestGenerator

print("=" * 80)
print("MODEL COMPARISON TEST")
print("=" * 80)
print()

# Test both models
models_to_test = [
    ("gpt-4.1", "GPT-4.1-nano (Original model)"),
    ("gpt-5.1-2", "GPT-5.1-2 (New model)")
]

for model_deployment, model_name in models_to_test:
    print(f"\n{'=' * 80}")
    print(f"Testing: {model_name}")
    print(f"Deployment: {model_deployment}")
    print(f"{'=' * 80}")

    # Update config for this model
    config.AZURE_OPENAI_DEPLOYMENT = model_deployment

    # Create fresh generator instance with updated config
    generator = SimpleTestGenerator()

    # Generate test cases
    result = generator.generate(
        user_prompt="Profiler DB upgrade",
        output_formats=[]  # Skip formatting for speed
    )

    if result['status'] == 'success':
        print(f"✅ SUCCESS")
        print(f"   Generated: {len(result['final_output'])} characters")
        print(f"   Test cases: {len(result['test_cases'])} parsed")
        print(f"   Categories: {list(set(tc['category'] for tc in result['test_cases']))}")
        print()
        print(f"   Sample test case:")
        if result['test_cases']:
            tc = result['test_cases'][0]
            print(f"   - ID: {tc.get('test_id', 'N/A')}")
            print(f"   - Title: {tc.get('title', 'N/A')[:80]}")
            print(f"   - Category: {tc.get('category', 'N/A')}")
            print(f"   - Priority: {tc.get('priority', 'N/A')}")
    else:
        print(f"❌ FAILED")
        print(f"   Error: {result.get('error', 'Unknown')}")

print()
print("=" * 80)
print("COMPARISON COMPLETE")
print("=" * 80)
print()
print("To switch models, edit config.py line 71:")
print("  AZURE_OPENAI_DEPLOYMENT = 'gpt-4.1'  # or 'gpt-5.1-2'")
print()
