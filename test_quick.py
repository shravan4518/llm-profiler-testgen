"""Quick test of GPT-5 generation"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.simple_testgen import SimpleTestGenerator

print("Testing GPT-5 generation...")
print()

generator = SimpleTestGenerator()

result = generator.generate(
    user_prompt="Profiler DB upgrade",
    output_formats=[]  # Skip formatting to see raw output faster
)

print()
print("=" * 80)
print(f"Status: {result['status']}")
if result['status'] == 'success':
    print(f"Generated: {len(result['final_output'])} characters")
    print(f"Test cases text length: {len(result['test_cases'])} characters")
    print()
    print("First 500 characters of output:")
    print(result['final_output'][:500])
else:
    print(f"Error: {result.get('error', 'Unknown')}")
print("=" * 80)
