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
        Supports both old models (GPT-4, GPT-4.1) and new models (GPT-5+)

        Args:
            prompt: User prompt
            system_message: Optional system message for context
            temperature: Optional temperature override
            max_tokens: Optional max tokens override (converted to max_completion_tokens for GPT-5+)

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

            # Prepare API parameters
            tokens_value = max_tokens or config.LLM_MAX_TOKENS
            api_params = {
                "model": self.deployment,
                "messages": messages,
                "temperature": temperature or config.LLM_TEMPERATURE
                # Note: top_p removed - GPT-5.1-2 doesn't support it
            }

            # Try with max_completion_tokens first (GPT-5+ models)
            # If that fails, fall back to max_tokens (older models)
            try:
                logger.debug(f"Trying max_completion_tokens={tokens_value}")
                response = self.client.chat.completions.create(
                    **api_params,
                    max_completion_tokens=tokens_value
                )
                logger.debug("Success with max_completion_tokens")
            except Exception as e:
                error_msg = str(e)
                logger.debug(f"First attempt with max_completion_tokens failed: {error_msg[:300]}")

                # Only retry with max_tokens if the error is SPECIFICALLY about max_completion_tokens being unsupported
                if ("max_completion_tokens" in error_msg and "unsupported" in error_msg.lower()) or \
                   ("max_completion_tokens" in error_msg and "not supported" in error_msg.lower()):
                    logger.info("Model doesn't support max_completion_tokens, trying max_tokens (GPT-4)")
                    response = self.client.chat.completions.create(
                        **api_params,
                        max_tokens=tokens_value
                    )
                else:
                    # Any other error (including temperature, top_p, etc.) - just raise it
                    logger.error(f"API error (not parameter compatibility): {type(e).__name__}")
                    raise

            # Extract response text
            logger.debug(f"Response object type: {type(response)}")
            logger.debug(f"Response has choices: {hasattr(response, 'choices')}")

            if not response or not response.choices:
                logger.error("No response or no choices in response")
                return ""

            logger.debug(f"Number of choices: {len(response.choices)}")
            logger.info(f"Finish reason: {response.choices[0].finish_reason}")  # Log finish reason to diagnose truncation

            content = response.choices[0].message.content
            logger.debug(f"Content type: {type(content)}, value: {repr(content[:200] if content else content)}")

            if content is None:
                logger.error("Response content is None")
                return ""

            result = content.strip()
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
