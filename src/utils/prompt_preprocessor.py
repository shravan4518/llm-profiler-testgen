"""
Prompt Preprocessing Layer
Analyzes and enriches user prompts for optimal RAG retrieval
"""
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import config
from src.utils.logger import setup_logger
from src.utils.azure_llm import get_azure_llm

logger = setup_logger(__name__)


class PromptPreprocessor:
    """
    Preprocesses user prompts to extract key information and generate
    optimized search queries for RAG retrieval
    """

    def __init__(self):
        """Initialize prompt preprocessor"""
        self.llm = get_azure_llm()
        logger.info("Prompt Preprocessor initialized")

    def analyze_prompt(self, user_prompt: str) -> Dict:
        """
        Analyze user prompt to extract intent and key entities

        Args:
            user_prompt: Raw user input

        Returns:
            Dictionary containing:
                - intent: Type of request (feature, bug, workflow, api, etc.)
                - feature_name: Extracted feature name
                - keywords: Key technical terms
                - entities: Identified entities (API endpoints, components, etc.)
                - search_queries: Optimized queries for RAG
        """
        logger.info("Analyzing user prompt...")

        system_message = """You are an expert at analyzing test case generation requests.
Extract key information from user prompts to help retrieve relevant documentation.

Identify:
1. Intent (feature description, workflow, API endpoint, configuration, etc.)
2. Feature/Component name
3. Technical keywords
4. Entities (endpoints, services, components)
5. Related concepts

Return response in this exact format:
INTENT: <intent_type>
FEATURE: <feature_name>
KEYWORDS: <comma,separated,keywords>
ENTITIES: <comma,separated,entities>
CONCEPTS: <comma,separated,related_concepts>"""

        prompt = f"""Analyze this test case generation request:

"{user_prompt}"

Extract all relevant information for documentation retrieval."""

        try:
            response = self.llm.generate(
                prompt=prompt,
                system_message=system_message,
                temperature=0.3,  # Lower temperature for precise extraction
                max_tokens=500
            )

            # Parse response
            analysis = self._parse_analysis(response)

            # Generate optimized search queries
            analysis['search_queries'] = self._generate_search_queries(analysis, user_prompt)

            logger.info(f"Prompt analysis complete: {analysis['intent']}")
            return analysis

        except Exception as e:
            logger.error(f"Prompt analysis failed: {e}")
            # Fallback to basic analysis
            return self._fallback_analysis(user_prompt)

    def _parse_analysis(self, response: str) -> Dict:
        """Parse LLM analysis response"""
        analysis = {
            'intent': 'general',
            'feature_name': '',
            'keywords': [],
            'entities': [],
            'concepts': []
        }

        lines = response.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('INTENT:'):
                analysis['intent'] = line.replace('INTENT:', '').strip().lower()
            elif line.startswith('FEATURE:'):
                analysis['feature_name'] = line.replace('FEATURE:', '').strip()
            elif line.startswith('KEYWORDS:'):
                keywords = line.replace('KEYWORDS:', '').strip()
                analysis['keywords'] = [k.strip() for k in keywords.split(',') if k.strip()]
            elif line.startswith('ENTITIES:'):
                entities = line.replace('ENTITIES:', '').strip()
                analysis['entities'] = [e.strip() for e in entities.split(',') if e.strip()]
            elif line.startswith('CONCEPTS:'):
                concepts = line.replace('CONCEPTS:', '').strip()
                analysis['concepts'] = [c.strip() for c in concepts.split(',') if c.strip()]

        return analysis

    def _generate_search_queries(self, analysis: Dict, original_prompt: str) -> List[str]:
        """
        Generate multiple optimized search queries for comprehensive RAG retrieval

        Args:
            analysis: Parsed prompt analysis
            original_prompt: Original user prompt

        Returns:
            List of optimized search queries
        """
        queries = []

        # Query 1: Original prompt (broad search)
        queries.append(original_prompt)

        # Query 2: Feature-focused query
        if analysis['feature_name']:
            queries.append(f"{analysis['feature_name']} functionality documentation")

        # Query 3: Entity-specific queries
        for entity in analysis['entities'][:2]:  # Top 2 entities
            queries.append(f"{entity} implementation details")

        # Query 4: Keyword combination
        if len(analysis['keywords']) >= 2:
            keyword_query = ' '.join(analysis['keywords'][:3])
            queries.append(f"{keyword_query} usage examples")

        # Query 5: Concept-based query
        if analysis['concepts']:
            queries.append(f"{analysis['concepts'][0]} architecture")

        # Remove duplicates while preserving order
        unique_queries = []
        seen = set()
        for q in queries:
            q_lower = q.lower()
            if q_lower not in seen:
                unique_queries.append(q)
                seen.add(q_lower)

        logger.info(f"Generated {len(unique_queries)} search queries")
        return unique_queries

    def _fallback_analysis(self, user_prompt: str) -> Dict:
        """Fallback analysis when LLM fails"""
        logger.warning("Using fallback prompt analysis")

        # Simple keyword extraction
        words = user_prompt.lower().split()
        keywords = [w for w in words if len(w) > 4][:5]

        return {
            'intent': 'general',
            'feature_name': user_prompt[:50],
            'keywords': keywords,
            'entities': [],
            'concepts': [],
            'search_queries': [user_prompt]
        }

    def enrich_context(self, user_prompt: str, rag_results: List[Dict]) -> str:
        """
        Enrich user prompt with RAG context for agent consumption

        Args:
            user_prompt: Original user prompt
            rag_results: Retrieved RAG results

        Returns:
            Enriched context string
        """
        context_parts = [
            "=== USER REQUEST ===",
            user_prompt,
            "",
            "=== RETRIEVED DOCUMENTATION CONTEXT ===",
        ]

        for idx, result in enumerate(rag_results, 1):
            context_parts.append(f"\n--- Context {idx} (Source: {result.get('file_path', 'Unknown')}) ---")
            context_parts.append(result.get('text', ''))

        enriched = '\n'.join(context_parts)
        logger.info(f"Enriched context created: {len(enriched)} characters")

        return enriched
