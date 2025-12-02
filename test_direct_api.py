"""Test Azure OpenAI API directly"""
import sys
from pathlib import Path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import config
from openai import AzureOpenAI

print("Testing Azure OpenAI API directly...")
print(f"Deployment: {config.AZURE_OPENAI_DEPLOYMENT}")
print(f"API Version: {config.AZURE_OPENAI_API_VERSION}")
print()

client = AzureOpenAI(
    azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
    api_key=config.AZURE_OPENAI_API_KEY,
    api_version=config.AZURE_OPENAI_API_VERSION
)

response = client.chat.completions.create(
    model=config.AZURE_OPENAI_DEPLOYMENT,
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Write 3 test cases for user login functionality"}
    ],
    temperature=1.0,
    max_completion_tokens=2000
)

print("Response:")
print(f"  Choices: {len(response.choices)}")
print(f"  Content: {response.choices[0].message.content}")
print(f"  Length: {len(response.choices[0].message.content)} characters")
print(f"  Finish reason: {response.choices[0].finish_reason}")
print(f"  Usage: {response.usage}")
