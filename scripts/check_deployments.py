"""
Check available Azure OpenAI deployments
Run this to see what models you can use
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import config
from openai import AzureOpenAI

print("=" * 80)
print("AZURE OPENAI DEPLOYMENT CHECKER")
print("=" * 80)
print()

print(f"Endpoint: {config.AZURE_OPENAI_ENDPOINT}")
print(f"Current Deployment: {config.AZURE_OPENAI_DEPLOYMENT}")
print()

print("=" * 80)
print("TESTING CURRENT DEPLOYMENT")
print("=" * 80)

try:
    client = AzureOpenAI(
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        api_key=config.AZURE_OPENAI_API_KEY,
        api_version=config.AZURE_OPENAI_API_VERSION
    )

    print(f"\nTrying deployment: {config.AZURE_OPENAI_DEPLOYMENT}")
    print("Sending test request...")

    # Try with max_completion_tokens first
    try:
        response = client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[{"role": "user", "content": "Hi"}],
            max_completion_tokens=10
        )
        print("[OK] Deployment works with max_completion_tokens (GPT-5+ model)")
        print(f"[OK] Response: {response.choices[0].message.content}")
        print(f"[OK] Model type: Newer model (GPT-5+)")
    except Exception as e1:
        if "max_completion_tokens" in str(e1) or "unsupported" in str(e1).lower():
            # Try with max_tokens
            try:
                response = client.chat.completions.create(
                    model=config.AZURE_OPENAI_DEPLOYMENT,
                    messages=[{"role": "user", "content": "Hi"}],
                    max_tokens=10
                )
                print("[OK] Deployment works with max_tokens (GPT-4 model)")
                print(f"[OK] Response: {response.choices[0].message.content}")
                print(f"[OK] Model type: Older model (GPT-4/GPT-4.1)")
            except Exception as e2:
                print(f"[ERROR] Failed with max_tokens too: {e2}")
                raise
        else:
            print(f"[ERROR] Deployment failed: {e1}")
            raise

    print()
    print("=" * 80)
    print("[SUCCESS] Current deployment is working!")
    print("=" * 80)

except Exception as e:
    print()
    print("=" * 80)
    print("[FAILED] Current deployment is NOT working")
    print("=" * 80)
    print(f"\nError: {e}")
    print()
    print("=" * 80)
    print("HOW TO FIX")
    print("=" * 80)
    print()
    print("1. Go to Azure Foundry portal:")
    print("   https://oai.azure.com/")
    print()
    print("2. Navigate to: Deployments (left sidebar)")
    print()
    print("3. Find your deployment name (NOT the model name)")
    print("   Example:")
    print("     - Deployment name: gpt-4-1-nano  <-- USE THIS")
    print("     - Model: gpt-4o-mini")
    print()
    print("4. Update config.py line 71:")
    print("   AZURE_OPENAI_DEPLOYMENT = 'your-deployment-name-here'")
    print()
    print("=" * 80)
