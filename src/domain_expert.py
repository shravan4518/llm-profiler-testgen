"""
Domain Expert: LLM-powered expert that understands product features, configurations, and test scenarios.

Similar to FrameworkExpert but for domain knowledge:
1. Training Phase: Analyzes documentation to build hierarchical concept graph
2. Query Phase: Uses concept graph to enrich test case generation context

Key innovations:
- Hierarchical concept extraction (Feature → Sub-features → Parameters)
- Image-aware document processing (diagrams show information flow)
- Concept relationship mapping (requires, extends, conflicts)
- Query-time concept expansion (main concept + related sub-concepts)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from openai import AzureOpenAI
from src.utils.logger import setup_logger
import PyPDF2
import re

logger = setup_logger(__name__)


class DomainExpert:
    """
    LLM-powered expert that understands product domain and builds hierarchical concept graphs.

    Solves the "generic test case" problem by:
    1. Building a mental model of features before generating tests
    2. Understanding concept hierarchies (Advanced Config → Parameter Validation → Boundary Testing)
    3. Capturing relationships between concepts that chunking destroys
    """

    def __init__(self, azure_client: AzureOpenAI, knowledge_dir: Path = None):
        self.client = azure_client
        self.knowledge_dir = knowledge_dir or Path("data/knowledge")
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)

        self.concept_graph = {}  # Hierarchical concept structure
        self.concept_index = {}  # Flat index for quick lookup
        self.knowledge_file = self.knowledge_dir / "domain_concepts.json"

        # Load existing knowledge if available
        if self.knowledge_file.exists():
            self._load_knowledge()
            logger.info(f"Loaded domain knowledge: {len(self.concept_graph)} top-level concepts")

    # ============================================================================
    # TRAINING PHASE: Build hierarchical concept graph from documents
    # ============================================================================

    def analyze_and_build_concept_graph(self, doc_path: Path, force_rebuild: bool = False) -> Dict:
        """
        ONE-TIME: Analyze documentation and build hierarchical concept graph.

        This is the critical step that solves your problem:
        - Extracts features as hierarchical concepts (not flat chunks)
        - Understands parent-child relationships
        - Maps configuration parameters to their feature
        - Identifies test-worthy scenarios per concept

        Args:
            doc_path: Path to PDF documentation (e.g., admin guide)
            force_rebuild: If True, rebuild even if knowledge exists

        Returns:
            Dictionary with analysis statistics
        """
        if self.knowledge_file.exists() and not force_rebuild:
            logger.info("Knowledge base already exists. Use force_rebuild=True to rebuild.")
            return self._get_status()

        logger.info(f"Starting document analysis: {doc_path}")

        # Step 1: Extract document content with structure preservation
        doc_content = self._extract_document_content(doc_path)

        # Step 2: Extract hierarchical concepts using LLM
        logger.info("Extracting hierarchical concepts from document...")
        concepts = self._extract_hierarchical_concepts(doc_content)

        # Step 3: Build concept graph with relationships
        logger.info("Building concept graph with relationships...")
        self._build_concept_graph(concepts)

        # Step 4: Extract test scenarios for each concept
        logger.info("Extracting test scenarios for each concept...")
        self._extract_test_scenarios()

        # Step 5: Save knowledge base
        self._save_knowledge()

        stats = self._get_status()
        stats['status'] = 'success'  # Override status for successful build
        logger.info(f"Domain knowledge built successfully: {stats}")
        return stats

    def _extract_document_content(self, doc_path: Path) -> Dict:
        """
        Extract content from PDF preserving structure (sections, subsections, tables, images).

        Critical: This preserves hierarchical structure that chunking destroys.

        IMPORTANT: Extracts ALL pages and analyzes images with their descriptions.
        """
        logger.info(f"Extracting content from: {doc_path}")

        content = {
            'sections': [],
            'images': [],
            'metadata': {
                'file_name': doc_path.name,
                'total_pages': 0
            }
        }

        try:
            with open(doc_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                content['metadata']['total_pages'] = total_pages

                logger.info(f"Processing ALL {total_pages} pages (NO truncation)...")

                full_text = []
                for page_num in range(total_pages):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()

                    # Add page markers to help preserve context
                    full_text.append(f"[PAGE {page_num + 1}]\n{page_text}")

                    # Extract images from page (if any)
                    if '/XObject' in page['/Resources']:
                        xobject = page['/Resources']['/XObject'].get_object()
                        for obj in xobject:
                            if xobject[obj]['/Subtype'] == '/Image':
                                # Record that page has images
                                content['images'].append({
                                    'page': page_num + 1,
                                    'note': 'Image present - context should be analyzed from surrounding text'
                                })

                # Combine ALL text (no truncation)
                combined_text = "\n\n".join(full_text)

                # Detect sections from FULL document
                sections = self._detect_sections(combined_text)
                content['sections'] = sections

                logger.info(f"Extracted {len(sections)} sections from ALL {total_pages} pages")
                logger.info(f"Found {len(content['images'])} images for context analysis")

        except Exception as e:
            logger.error(f"Error extracting PDF content: {e}")
            raise

        return content

    def _detect_sections(self, text: str) -> List[Dict]:
        """
        Detect major sections in document text.

        Simple heuristic: Lines in ALL CAPS or with Chapter/Section numbering
        """
        lines = text.split('\n')
        sections = []
        current_section = None
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this is a section heading
            # Heuristics: ALL CAPS, starts with Chapter/Section, or short line followed by content
            is_heading = (
                line.isupper() and len(line.split()) <= 10 or
                re.match(r'^(Chapter|Section|CHAPTER|SECTION|\d+\.)\s+', line) or
                (len(line.split()) <= 8 and len(line) < 80)
            )

            if is_heading and len(line) > 5:
                # Save previous section
                if current_section:
                    sections.append({
                        'title': current_section,
                        'content': '\n'.join(current_content)
                    })

                # Start new section
                current_section = line
                current_content = []
            else:
                current_content.append(line)

        # Add last section
        if current_section and current_content:
            sections.append({
                'title': current_section,
                'content': '\n'.join(current_content)
            })

        return sections

    def _extract_hierarchical_concepts(self, doc_content: Dict) -> List[Dict]:
        """
        Use LLM to extract hierarchical concepts from document.

        This is the KEY innovation: Extract concepts as a TREE, not flat chunks.

        CRITICAL: Process ALL sections with NO truncation to capture complete admin guide.

        Example output:
        {
          "name": "Advanced Configuration",
          "type": "feature",
          "description": "...",
          "sub_concepts": [
            {
              "name": "Parameter Validation",
              "type": "sub-feature",
              "parameters": ["sampling_rate", "buffer_size"],
              ...
            }
          ],
          "test_dimensions": ["configuration", "validation", "persistence"],
          "relationships": [...]
        }
        """
        # Build prompt with ALL sections (NO truncation)
        logger.info(f"Processing ALL {len(doc_content['sections'])} sections (NO limits)")

        sections_text = "\n\n".join([
            f"=== {section['title']} ===\n{section['content']}"  # NO truncation
            for section in doc_content['sections']  # ALL sections
        ])

        # Add image context
        image_context = ""
        if doc_content.get('images'):
            image_context = f"\n\nIMAGES FOUND: The document contains {len(doc_content['images'])} images. " \
                          "Analyze surrounding text context to understand diagrams, screenshots, and workflows depicted in images."

        prompt = f"""Analyze the COMPLETE product documentation (ALL {doc_content['metadata']['total_pages']} pages) and extract ALL features/concepts in a HIERARCHICAL structure.

CRITICAL REQUIREMENTS:
1. Extract EVERY feature/concept mentioned in the document (NOT just first few)
2. Maintain EXACT hierarchical structure as it appears in the document
3. Analyze text surrounding images to understand visual content
4. Do NOT skip any sections - process the ENTIRE document

DOCUMENTATION:
{sections_text}{image_context}

TASK:
Extract features as a hierarchical tree. For each feature:
1. Identify main features (e.g., "Advanced Configuration", "Database Management")
2. Identify sub-features under each main feature
3. Extract configuration parameters for each feature
4. Identify relationships between features (requires, extends, conflicts)
5. Determine what makes this feature test-worthy (constraints, edge cases, failure modes)

Return as structured JSON:
{{
  "concepts": [
    {{
      "name": "Advanced Configuration",
      "type": "feature",
      "description": "Detailed description of this feature",
      "sub_concepts": [
        {{
          "name": "Sampling Rate Configuration",
          "type": "configuration",
          "description": "...",
          "parameters": [
            {{
              "name": "sampling_rate",
              "type": "integer",
              "range": "1-100",
              "default": 10,
              "constraints": ["Must be between 1-100", "Higher values impact performance"]
            }}
          ],
          "validation_rules": ["..."],
          "failure_modes": ["Invalid value", "Out of range", "Performance degradation"]
        }}
      ],
      "test_dimensions": [
        "Parameter validation",
        "Boundary value testing",
        "Persistence verification",
        "Error handling",
        "Performance impact"
      ],
      "relationships": [
        {{"related_to": "Basic Configuration", "type": "extends"}},
        {{"related_to": "Performance Monitoring", "type": "affects"}}
      ],
      "prerequisites": ["Basic Configuration must be completed first"],
      "search_terms": ["advanced config", "configuration parameters", "profiler settings"]
    }}
  ]
}}

IMPORTANT:
- Extract HIERARCHICAL structure (main feature → sub-features → parameters)
- Include ALL configuration parameters with their constraints
- Identify failure modes and edge cases for testing
- Map relationships between features
- Be comprehensive - this drives test quality

Return ONLY valid JSON, no other text."""

        try:
            logger.info("Calling LLM to extract hierarchical concepts...")
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Use GPT-4o for document analysis
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert documentation analyzer. Extract hierarchical feature concepts for test generation. Return ONLY valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_completion_tokens=16000  # Large output for comprehensive extraction
            )

            result_text = response.choices[0].message.content

            # Extract JSON from response
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            concepts_data = json.loads(result_text)
            logger.info(f"Extracted {len(concepts_data.get('concepts', []))} top-level concepts")

            return concepts_data.get('concepts', [])

        except Exception as e:
            logger.error(f"Error extracting concepts: {e}")
            raise

    def _build_concept_graph(self, concepts: List[Dict]):
        """
        Build hierarchical concept graph from extracted concepts.

        Structure:
        - self.concept_graph: Hierarchical tree (feature → sub-features)
        - self.concept_index: Flat index for quick lookup by name
        """
        self.concept_graph = {}
        self.concept_index = {}

        for concept in concepts:
            concept_name = concept['name']
            self.concept_graph[concept_name] = concept

            # Add to flat index
            self.concept_index[concept_name.lower()] = concept

            # Also index sub-concepts
            for sub_concept in concept.get('sub_concepts', []):
                sub_name = sub_concept['name']
                self.concept_index[sub_name.lower()] = {
                    **sub_concept,
                    'parent_concept': concept_name
                }

            # Index search terms
            for term in concept.get('search_terms', []):
                if term.lower() not in self.concept_index:
                    self.concept_index[term.lower()] = concept

        logger.info(f"Built concept graph: {len(self.concept_graph)} main concepts, {len(self.concept_index)} indexed terms")

    def _extract_test_scenarios(self):
        """
        For each concept, generate test scenario templates using LLM.

        This creates reusable test patterns for each feature.
        """
        for concept_name, concept in self.concept_graph.items():
            try:
                # Build prompt for test scenario extraction
                prompt = f"""Given the following feature definition, generate comprehensive test scenario templates.

FEATURE: {concept_name}
DESCRIPTION: {concept.get('description', '')}
SUB-FEATURES: {', '.join([sc['name'] for sc in concept.get('sub_concepts', [])])}
TEST DIMENSIONS: {', '.join(concept.get('test_dimensions', []))}

Generate test scenarios covering:
1. Happy path scenarios
2. Boundary value scenarios
3. Error/negative scenarios
4. Integration scenarios (if relationships exist)
5. Performance/edge case scenarios

Return as JSON array of test scenarios:
[
  {{
    "scenario": "Validate advanced configuration with valid parameters",
    "test_type": "positive",
    "priority": "high",
    "preconditions": ["..."],
    "test_steps": ["..."],
    "expected_results": ["..."]
  }}
]

Return ONLY valid JSON."""

                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a test architect. Generate comprehensive test scenarios. Return ONLY valid JSON."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.2,
                    max_completion_tokens=4000
                )

                result_text = response.choices[0].message.content

                # Extract JSON
                if '```json' in result_text:
                    result_text = result_text.split('```json')[1].split('```')[0].strip()
                elif '```' in result_text:
                    result_text = result_text.split('```')[1].split('```')[0].strip()

                scenarios = json.loads(result_text)
                concept['test_scenarios'] = scenarios

                logger.info(f"Generated {len(scenarios)} test scenarios for {concept_name}")

            except Exception as e:
                logger.warning(f"Could not generate test scenarios for {concept_name}: {e}")
                concept['test_scenarios'] = []

    # ============================================================================
    # QUERY PHASE: Enrich context for test generation
    # ============================================================================

    def get_enriched_context(self, user_query: str, rag_chunks: List[str] = None) -> Dict:
        """
        RUNTIME: Get enriched context for test case generation.

        This is called during test generation to provide comprehensive context:
        1. Identify relevant concepts from query
        2. Get full concept hierarchy (parent + children)
        3. Get related concepts
        4. Get test scenario templates
        5. Enhance RAG results with concept knowledge

        Returns:
        {
            'primary_concepts': [...],  # Main concepts identified
            'concept_hierarchy': {...},  # Full hierarchical structure
            'related_concepts': [...],  # Related concepts to consider
            'test_scenarios': [...],  # Pre-defined test scenario templates
            'test_strategy': {...},  # Reasoning about what to test
            'enhanced_rag_context': [...]  # RAG chunks with concept enrichment
        }
        """
        logger.info(f"Enriching context for query: {user_query}")

        # Step 1: Identify relevant concepts from query
        relevant_concepts = self._identify_concepts_from_query(user_query)

        # Step 2: Expand to include parent/child concepts
        expanded_concepts = self._expand_concept_hierarchy(relevant_concepts)

        # Step 3: Get related concepts through relationships
        related_concepts = self._get_related_concepts(expanded_concepts)

        # Step 4: Generate test strategy
        test_strategy = self._generate_test_strategy(expanded_concepts, user_query)

        # Step 5: Get test scenario templates
        test_scenarios = self._get_test_scenarios(expanded_concepts)

        return {
            'primary_concepts': relevant_concepts,
            'concept_hierarchy': expanded_concepts,
            'related_concepts': related_concepts,
            'test_scenarios': test_scenarios,
            'test_strategy': test_strategy,
            'enhanced_rag_context': rag_chunks or [],
            'status': 'success'
        }

    def _identify_concepts_from_query(self, query: str) -> List[Dict]:
        """
        Use LLM to identify which concepts from our knowledge base are relevant to the query.
        """
        available_concepts = list(self.concept_graph.keys())

        prompt = f"""Given a user query and available concepts, identify which concepts are relevant.

USER QUERY: {query}

AVAILABLE CONCEPTS:
{json.dumps(available_concepts, indent=2)}

Return the relevant concept names as a JSON array:
["Concept 1", "Concept 2", ...]

Return ONLY the JSON array."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a concept mapper. Identify relevant concepts from query. Return ONLY valid JSON array."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_completion_tokens=500
            )

            result_text = response.choices[0].message.content.strip()

            # Extract JSON array
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            concept_names = json.loads(result_text)

            # Get full concept objects
            concepts = [self.concept_graph[name] for name in concept_names if name in self.concept_graph]

            logger.info(f"Identified {len(concepts)} relevant concepts from query")
            return concepts

        except Exception as e:
            logger.warning(f"Error identifying concepts: {e}. Falling back to keyword matching.")
            # Fallback: Simple keyword matching
            query_lower = query.lower()
            concepts = []
            for name, concept in self.concept_graph.items():
                if any(term.lower() in query_lower for term in [name] + concept.get('search_terms', [])):
                    concepts.append(concept)
            return concepts

    def _expand_concept_hierarchy(self, concepts: List[Dict]) -> List[Dict]:
        """
        Expand concepts to include parent and child concepts.

        If user asks about "Parameter Validation" (sub-concept),
        we also include "Advanced Configuration" (parent concept).
        """
        expanded = list(concepts)  # Start with original concepts

        for concept in concepts:
            # Add parent if exists
            if 'parent_concept' in concept:
                parent_name = concept['parent_concept']
                if parent_name in self.concept_graph:
                    parent = self.concept_graph[parent_name]
                    if parent not in expanded:
                        expanded.append(parent)

            # Add all sub-concepts
            for sub_concept in concept.get('sub_concepts', []):
                if sub_concept not in expanded:
                    expanded.append(sub_concept)

        return expanded

    def _get_related_concepts(self, concepts: List[Dict]) -> List[Dict]:
        """
        Get related concepts through relationship mappings.
        """
        related = []

        for concept in concepts:
            for relationship in concept.get('relationships', []):
                related_name = relationship.get('related_to')
                if related_name and related_name in self.concept_graph:
                    related_concept = self.concept_graph[related_name]
                    if related_concept not in related and related_concept not in concepts:
                        related.append(related_concept)

        return related

    def _generate_test_strategy(self, concepts: List[Dict], user_query: str) -> Dict:
        """
        Generate test strategy using LLM.

        This forces the LLM to THINK before generating test cases.
        """
        concepts_summary = json.dumps([
            {
                'name': c['name'],
                'test_dimensions': c.get('test_dimensions', []),
                'failure_modes': [sc.get('failure_modes', []) for sc in c.get('sub_concepts', [])]
            }
            for c in concepts
        ], indent=2)

        prompt = f"""As a senior test architect, create a test strategy for the following request.

USER REQUEST: {user_query}

RELEVANT CONCEPTS:
{concepts_summary}

Create a comprehensive test strategy explaining:
1. What should be tested and why (test objectives)
2. Test dimensions to cover (config, boundaries, errors, integration, performance)
3. Priority areas (what's most risky/important)
4. Expected coverage (positive, negative, edge cases)

Return as JSON:
{{
  "test_objectives": ["Validate X", "Ensure Y"],
  "test_dimensions": ["configuration", "validation", "boundaries", "error_handling"],
  "priority_areas": ["High-risk area 1", "Critical path 2"],
  "coverage_strategy": {{
    "positive_tests": "Percentage or count",
    "negative_tests": "Percentage or count",
    "edge_cases": "Percentage or count"
  }},
  "reasoning": "Explanation of test strategy"
}}

Return ONLY valid JSON."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior test architect. Create comprehensive test strategies. Return ONLY valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_completion_tokens=2000
            )

            result_text = response.choices[0].message.content

            # Extract JSON
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()

            strategy = json.loads(result_text)
            return strategy

        except Exception as e:
            logger.error(f"Error generating test strategy: {e}")
            return {
                'test_objectives': [],
                'test_dimensions': [],
                'priority_areas': [],
                'coverage_strategy': {},
                'reasoning': 'Strategy generation failed'
            }

    def _get_test_scenarios(self, concepts: List[Dict]) -> List[Dict]:
        """
        Get all test scenario templates for the given concepts.
        """
        scenarios = []
        for concept in concepts:
            scenarios.extend(concept.get('test_scenarios', []))
        return scenarios

    # ============================================================================
    # PERSISTENCE
    # ============================================================================

    def _save_knowledge(self):
        """Save concept graph to disk."""
        knowledge_data = {
            'concept_graph': self.concept_graph,
            'concept_index': self.concept_index,
            'metadata': {
                'total_concepts': len(self.concept_graph),
                'total_indexed_terms': len(self.concept_index)
            }
        }

        with open(self.knowledge_file, 'w', encoding='utf-8') as f:
            json.dump(knowledge_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved domain knowledge to {self.knowledge_file}")

    def _load_knowledge(self):
        """Load concept graph from disk."""
        try:
            with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                knowledge_data = json.load(f)

            self.concept_graph = knowledge_data.get('concept_graph', {})
            self.concept_index = knowledge_data.get('concept_index', {})

            logger.info("Loaded domain knowledge from disk")
        except Exception as e:
            logger.error(f"Error loading knowledge: {e}")
            self.concept_graph = {}
            self.concept_index = {}

    def _get_status(self) -> Dict:
        """Get status of knowledge base."""
        return {
            'status': 'ready' if self.concept_graph else 'not_analyzed',
            'total_concepts': len(self.concept_graph),
            'total_indexed_terms': len(self.concept_index),
            'knowledge_file': str(self.knowledge_file),
            'file_exists': self.knowledge_file.exists()
        }

    def get_status(self) -> Dict:
        """Public method to get status."""
        return self._get_status()
