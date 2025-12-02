"""Dump raw GPT-5 output to see formatting"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.simple_testgen import SimpleTestGenerator

generator = SimpleTestGenerator()
result = generator.generate(
    user_prompt="Profiler DB upgrade",
    output_formats=[]
)

if result['status'] == 'success':
    raw_output = result['final_output']

    # Save to file
    with open('gpt5_raw_output.txt', 'w', encoding='utf-8') as f:
        f.write(raw_output)

    print(f"Saved {len(raw_output)} characters to gpt5_raw_output.txt")
    print()
    print("First 2000 characters:")
    print("=" * 80)
    print(raw_output[:2000])
else:
    print(f"Error: {result.get('error')}")
