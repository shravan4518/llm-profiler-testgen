"""
Azure OpenAI LLM Integration
Provides unified interface for Azure OpenAI GPT-4.1-nano
"""
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import config
from src.utils.logger import setup_logger
from openai import AzureOpenAI
from langchain_openai import AzureChatOpenAI

logger = setup_logger(__name__)


class AzureLLM:
    """
    Azure OpenAI LLM wrapper for test case generation
    Supports both direct API calls and LangChain integration
    """

    def __init__(self):
        """Initialize Azure OpenAI client"""
        self.endpoint = config.AZURE_OPENAI_ENDPOINT
        self.api_key = config.AZURE_OPENAI_API_KEY
        self.deployment = config.AZURE_OPENAI_DEPLOYMENT
        self.api_version = config.AZURE_OPENAI_API_VERSION

        # Validate configuration
        if not self.endpoint or not self.api_key:
            raise ValueError(
                "Azure OpenAI credentials not configured. "
                "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables."
            )

        # Initialize OpenAI client
        self.client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version
        )

        # Initialize LangChain client for CrewAI
        self.langchain_llm = AzureChatOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
            azure_deployment=self.deployment,
            temperature=config.LLM_TEMPERATURE,
            max_tokens=config.LLM_MAX_TOKENS,
            top_p=config.LLM_TOP_P
        )

        logger.info(f"Azure OpenAI initialized: {self.deployment}")

    def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text using Azure OpenAI

        Args:
            prompt: User prompt
            system_message: Optional system message for context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override

        Returns:
            Generated text response
        """
        try:
            messages = []

            # Add system message if provided
            if system_message:
                messages.append({"role": "system", "content": system_message})

            # Add user prompt
            messages.append({"role": "user", "content": prompt})

            # Call Azure OpenAI
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=temperature or config.LLM_TEMPERATURE,
                max_tokens=max_tokens or config.LLM_MAX_TOKENS,
                top_p=config.LLM_TOP_P
            )

            # Extract response text
            result = response.choices[0].message.content.strip()

            logger.info(f"Generated {len(result)} characters")
            return result

        except Exception as e:
            logger.error(f"Azure OpenAI generation error: {e}")
            raise

    def get_langchain_llm(self) -> AzureChatOpenAI:
        """
        Get LangChain-compatible LLM instance for CrewAI

        Returns:
            LangChain AzureChatOpenAI instance
        """
        return self.langchain_llm

    def is_available(self) -> bool:
        """
        Check if Azure OpenAI is properly configured

        Returns:
            True if configured and accessible
        """
        try:
            # Test with a simple prompt
            test_response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            return test_response is not None
        except Exception as e:
            logger.error(f"Azure OpenAI availability check failed: {e}")
            return False


# Global LLM instance (singleton pattern)
_llm_instance = None

def get_azure_llm() -> AzureLLM:
    """
    Get global Azure LLM instance (singleton)

    Returns:
        AzureLLM instance
    """
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = AzureLLM()
    return _llm_instance
