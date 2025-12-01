"""
LLM-powered Q&A Module
Uses Gemini API to generate answers based on retrieved document chunks
"""
import sys
from pathlib import Path
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed. LLM Q&A features will be disabled.")


class GeminiQA:
    """Gemini-powered Q&A system for RAG results"""

    def __init__(self):
        """Initialize Gemini API"""
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-generativeai package not found. "
                "Install with: pip install google-generativeai"
            )

        if not config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not configured in config.py")

        try:
            genai.configure(api_key=config.GEMINI_API_KEY)

            # Configure safety settings to be more permissive for technical documentation
            # Note: Free tier may have limitations on safety settings
            # Try BLOCK_NONE for technical content (may not work on all free tier accounts)
            try:
                safety_settings = [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE"
                    },
                ]
                logger.info("Attempting to use BLOCK_NONE safety settings for technical documentation")
            except Exception:
                # Fallback to BLOCK_MEDIUM_AND_ABOVE if BLOCK_NONE not allowed
                safety_settings = [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                ]
                logger.info("Falling back to BLOCK_MEDIUM_AND_ABOVE safety settings")

            self.model = genai.GenerativeModel(
                config.GEMINI_MODEL,
                safety_settings=safety_settings
            )
            logger.info(f"Gemini API initialized with model: {config.GEMINI_MODEL}")
            logger.info(f"Safety settings configured: BLOCK_MEDIUM_AND_ABOVE for all categories")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini API: {e}")
            raise

    def generate_answer(
        self,
        query: str,
        chunks: List[str]
    ) -> Optional[str]:
        """
        Generate an answer to the query based on retrieved chunks

        Args:
            query: The user's original search query
            chunks: List of retrieved text chunks

        Returns:
            LLM-generated answer or None if error occurs
        """
        if not chunks:
            logger.warning("No chunks provided for Q&A generation")
            return None

        try:
            # Combine all chunks into context - limit to first 3000 chars per chunk for free tier
            truncated_chunks = []
            for i, chunk in enumerate(chunks):
                # Truncate very long chunks to avoid overwhelming the free tier API
                chunk_text = chunk[:3000] if len(chunk) > 3000 else chunk
                truncated_chunks.append(chunk_text)

            context = "\n\n".join(truncated_chunks)

            # Further limit total context size for free tier stability
            if len(context) > 8000:
                logger.warning(f"Context too large ({len(context)} chars), truncating to 8000 chars for free tier compatibility")
                context = context[:8000] + "\n\n[... content truncated for API limits ...]"

            # Build prompt - extremely simplified for free tier
            prompt = f"""Answer this question using the documentation below.

Question: {query}

Documentation:
{context}

Answer:"""

            # Generate response
            logger.info(f"Generating LLM answer for query: {query}")
            logger.debug(f"Context size: {len(context)} characters, {len(chunks)} chunks")

            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=config.LLM_TEMPERATURE,
                    max_output_tokens=config.LLM_MAX_TOKENS,
                )
            )

            # Debug: Log response structure
            logger.debug(f"Response received: {response is not None}")
            if response:
                logger.debug(f"Response has candidates: {hasattr(response, 'candidates') and bool(response.candidates)}")
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    logger.debug(f"First candidate finish_reason: {candidate.finish_reason if hasattr(candidate, 'finish_reason') else 'N/A'}")

            # Check response validity and handle safety blocks
            if response:
                try:
                    # Try to access the text - this will raise ValueError if blocked
                    answer_text = response.text

                    # Check if response seems truncated or incomplete
                    if answer_text and len(answer_text) < 50:
                        logger.warning(f"Response seems very short ({len(answer_text)} chars), may be truncated")
                        # Still return it but log the concern

                    if answer_text:
                        logger.info(f"LLM answer generated successfully ({len(answer_text)} chars)")
                        return answer_text
                    else:
                        logger.warning("LLM returned empty text")
                        return "⚠ The LLM returned an empty response. Try using fewer search results or rephrasing your query."
                except ValueError as e:
                    # Handle cases where response.text fails (e.g., safety blocks)
                    logger.warning(f"Could not access response.text: {e}")

                    # Try to get information about why it failed
                    if hasattr(response, 'prompt_feedback'):
                        logger.warning(f"Prompt feedback: {response.prompt_feedback}")

                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'finish_reason'):
                            finish_reason = candidate.finish_reason
                            logger.warning(f"Finish reason: {finish_reason}")

                            # Provide user-friendly error messages
                            if finish_reason == 2:  # SAFETY
                                logger.info("Returning safety block message to user")
                                return "⚠ The LLM response was blocked due to safety filters. This may happen if the content is flagged as potentially sensitive. Try rephrasing your query or reducing the amount of retrieved content."
                            elif finish_reason == 3:  # RECITATION
                                logger.info("Returning recitation block message to user")
                                return "⚠ The LLM response was blocked due to recitation concerns (potential copyright issues). Try a different query."
                            elif finish_reason == 4:  # OTHER
                                logger.info("Returning other failure message to user")
                                return "⚠ The LLM could not generate a response due to other reasons. Please try again with a different query."

                    logger.warning("Could not determine specific failure reason")
                    return "⚠ The LLM could not generate a response. This may be due to content filtering or API limitations. Try rephrasing your query or using fewer search results."
            else:
                logger.warning("LLM returned empty response")
                return None

        except ValueError as ve:
            # Catch ValueError at the outer level too
            logger.error(f"ValueError generating LLM answer: {ve}")
            return "⚠ The LLM encountered an error processing your request. This may be due to content filtering. Try rephrasing your query or using fewer search results."
        except Exception as e:
            # Catch any other exceptions
            logger.error(f"Unexpected error generating LLM answer: {e}")
            return None

    def is_available(self) -> bool:
        """Check if Gemini API is available and configured"""
        return GEMINI_AVAILABLE and bool(config.GEMINI_API_KEY)


def generate_qa_answer(query: str, chunks: List[str]) -> Optional[str]:
    """
    Convenience function to generate Q&A answer

    Args:
        query: User's search query
        chunks: List of retrieved text chunks

    Returns:
        LLM-generated answer or None
    """
    if not config.USE_LLM_QA:
        logger.debug("LLM Q&A is disabled in config")
        return None

    try:
        qa = GeminiQA()
        return qa.generate_answer(query, chunks)
    except Exception as e:
        logger.error(f"Failed to generate Q&A answer: {e}")
        return None
