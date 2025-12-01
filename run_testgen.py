"""
Quick Start Script for AI-Powered Test Case Generator
Run this script to generate test cases from feature descriptions
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """Main entry point"""
    print("\n" + "=" * 80)
    print("AI-POWERED TEST CASE GENERATOR")
    print("Powered by Azure OpenAI + CrewAI Multi-Agent System")
    print("=" * 80)
    print()

    # Check configuration
    import config

    if not config.AZURE_OPENAI_ENDPOINT or not config.AZURE_OPENAI_API_KEY:
        print("⚠️  ERROR: Azure OpenAI not configured!")
        print()
        print("Please set the following environment variables:")
        print("  - AZURE_OPENAI_ENDPOINT")
        print("  - AZURE_OPENAI_API_KEY")
        print("  - AZURE_OPENAI_DEPLOYMENT (optional, defaults to 'gpt-4-1-nano')")
        print()
        print("Or edit config.py to set these values directly.")
        print()
        return

    # Check CrewAI availability
    try:
        from src.testcase_generator import TestCaseGenerator

        print("✓ Azure OpenAI configured")
        print(f"✓ Endpoint: {config.AZURE_OPENAI_ENDPOINT}")
        print(f"✓ Deployment: {config.AZURE_OPENAI_DEPLOYMENT}")
        print()

        # Run interactive mode
        generator = TestCaseGenerator()
        generator.generate_interactive()

    except ImportError as e:
        print("⚠️  CrewAI not installed (Python 3.14 compatibility issue)")
        print()
        print("Alternative: Use direct Azure OpenAI integration")
        print()
        print("To install CrewAI:")
        print("  1. Use Python 3.10-3.13")
        print("  2. Run: pip install crewai crewai-tools")
        print()
        print(f"Error details: {e}")
        print()

if __name__ == "__main__":
    main()
