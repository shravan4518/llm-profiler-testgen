"""
Quick Start - Simplified Test Case Generator
Fast, simple, single Azure OpenAI call approach
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """Main entry point"""
    print("\n" + "=" * 80)
    print("SIMPLIFIED AI-POWERED TEST CASE GENERATOR")
    print("Fast & Efficient - Single Azure OpenAI Call")
    print("=" * 80)
    print()

    # Check configuration
    import config

    if not config.AZURE_OPENAI_ENDPOINT or not config.AZURE_OPENAI_API_KEY:
        print("[ERROR] Azure OpenAI not configured!")
        print()
        print("Please set the following environment variables:")
        print()
        print("Windows PowerShell:")
        print('  $env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"')
        print('  $env:AZURE_OPENAI_API_KEY = "your-api-key-here"')
        print('  $env:AZURE_OPENAI_DEPLOYMENT = "gpt-4-1-nano"')
        print()
        print("OR edit config.py directly (lines 56-58)")
        print()
        return

    try:
        from src.simple_testgen import SimpleTestGenerator

        print("[OK] Azure OpenAI configured")
        print(f"[OK] Endpoint: {config.AZURE_OPENAI_ENDPOINT}")
        print(f"[OK] Deployment: {config.AZURE_OPENAI_DEPLOYMENT}")
        print()

        # Run interactive mode
        generator = SimpleTestGenerator()
        generator.generate_interactive()

    except Exception as e:
        print(f"[ERROR] {e}")
        print()
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
