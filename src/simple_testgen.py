"""
Simplified AI-Powered Test Case Generator
Single Azure OpenAI call approach - Fast, Simple, Effective

Workflow: User Prompt → RAG Retrieval → Single Optimized Azure OpenAI Call → Test Cases
"""
import sys
from pathlib import Path
from typing import Dict, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import config
from src.utils.logger import setup_logger
from src.utils.azure_llm import get_azure_llm
from src.utils.prompt_preprocessor import PromptPreprocessor
from src.utils.output_formatter import TestCaseFormatter
from src.vector_db.vector_store import VectorStore
from src.vector_db.search_engine import HybridSearchEngine
from src.vector_db.enhanced_retrieval import EnhancedRetrieval
from src.pkg_loader import PKGLoader

logger = setup_logger(__name__)


class SimpleTestGenerator:
    """
    Simplified AI-Powered Test Case Generator
    Uses single optimized Azure OpenAI call instead of multi-agent orchestration
    """

    def __init__(self, domain_expert=None):
        """Initialize test case generator

        Args:
            domain_expert: Optional DomainExpert instance for hierarchical concept enrichment
        """
        logger.info("=" * 80)
        logger.info("Initializing Simplified AI Test Case Generator")
        logger.info("=" * 80)

        # Initialize components
        logger.info("Loading RAG components...")
        self.vector_store = VectorStore()
        self.search_engine = HybridSearchEngine(self.vector_store)
        self.enhanced_retrieval = EnhancedRetrieval(self.search_engine)

        logger.info("Loading Azure OpenAI...")
        self.azure_llm = get_azure_llm()

        logger.info("Loading utilities...")
        self.prompt_preprocessor = PromptPreprocessor()
        self.formatter = TestCaseFormatter()

        # Domain Expert for hierarchical concept understanding
        self.domain_expert = domain_expert
        if domain_expert:
            logger.info("Domain Expert integration enabled")

        # PKG Loader for structured product knowledge
        pkg_dir = Path(config.DATA_DIR) / "pkg"
        if pkg_dir.exists():
            # Pass the raw AzureOpenAI client, not the AzureLLM wrapper
            self.pkg_loader = PKGLoader(pkg_dir, self.azure_llm.client)
            logger.info(f"PKG Loader initialized: {self.pkg_loader.get_status()['total_features']} features")
        else:
            self.pkg_loader = None
            logger.warning(f"PKG directory not found: {pkg_dir}. PKG-based generation disabled.")

        logger.info("=" * 80)
        logger.info("Test Case Generator initialized successfully")
        logger.info("=" * 80)

    def _build_master_prompt(self, user_prompt: str, rag_context: str) -> str:
        """
        Build comprehensive master prompt that replaces multi-agent workflow

        Args:
            user_prompt: Original user request
            rag_context: Retrieved documentation context

        Returns:
            Optimized prompt for single LLM call
        """

        system_prompt = """You are an elite QA Test Architect and Test Case Designer with 20+ years of experience in enterprise software testing. You have expertise in:

- IEEE 829 and ISO/IEC/IEEE 29119 testing standards
- Comprehensive test coverage analysis
- Test case design for maximum defect detection
- Security, performance, and integration testing
- Boundary value analysis and equivalence partitioning
- Risk-based testing strategies

Your test cases are known for being:
- Exhaustively comprehensive (covering ALL scenarios)
- Precisely detailed (executable by any tester)
- Properly categorized (positive, negative, boundary, integration, security, performance)
- Production-ready (following industry standards)

You NEVER miss edge cases or error scenarios."""

        user_instruction = f"""Generate SPECIFIC test cases for the following requirement.

=== USER REQUIREMENT ===
{user_prompt}

=== CONTEXT SOURCES (Prioritized) ===
{rag_context}

=== YOUR TASK ===

🎯 CRITICAL INSTRUCTIONS 🎯

**1. DATA SOURCE PRIORITY:**
   - **PRIMARY:** Product Knowledge Graph (PKG) - Use EXACT field names, types, ranges, defaults from PKG
   - **SECONDARY:** Domain Knowledge - Use for hierarchical concepts and test strategy
   - **TERTIARY:** RAG Context - Use for additional context and descriptions only

**2. PKG FIELDS ARE MANDATORY:**
   - If PKG section exists, you MUST use the exact input field names listed
   - You MUST use the exact ranges, defaults, and validation rules from PKG
   - You MUST use the exact navigation paths from PKG UI surfaces
   - You MUST reference constraints from PKG

**3. NO GENERIC TEST CASES:**
   - DO NOT write "Verify configuration saves" → Write "Click Save Changes button and verify polling_interval=720 persists"
   - DO NOT write "Test with invalid input" → Write "Enter polling_interval=0 (below min=1) and verify error"
   - DO NOT write "Navigate to configuration page" → Write "Navigate to Profiler -> Profiler Configuration -> Advance Configuration"

**4. REQUIRED SPECIFICITY:**
   Every test case MUST include:
   - EXACT field name from PKG (e.g., "polling_interval", not "interval")
   - EXACT range/default from PKG (e.g., "range: 1-1440, default: 720")
   - EXACT navigation path from PKG (e.g., "Profiler -> Configuration -> Advance")
   - EXACT button/action names from PKG (e.g., "Start On-Demand Scan")

⚠️ EXAMPLES ⚠️
❌ BAD (Generic): "Verify polling configuration saves"
✅ GOOD (PKG-based): "Set polling_interval=720 (default) in Device Attribute Server Configuration section and click Save Changes"

❌ BAD (Generic): "Test boundary values"
✅ GOOD (PKG-based): "Set polling_interval=1 (min boundary), verify acceptance. Set polling_interval=1440 (max boundary), verify acceptance. Set polling_interval=1441 (above max), verify rejection."

❌ BAD (Generic): "Navigate to advanced settings"
✅ GOOD (PKG-based): "Navigate to Profiler -> Profiler Configuration -> Advance Configuration screen"

⚠️ START IMMEDIATELY WITH TEST CASES ⚠️
Do NOT write introductions or analysis. Your first line MUST be a test case heading.

===SECTION 1: SPECIFIC TEST CASES (from documentation)===

Generate test cases using ONLY specific details found in the documentation above:

**POSITIVE TEST CASES (30-40% of total):**
- Happy path scenarios with valid inputs
- Standard user workflows
- Expected functionality verification

**NEGATIVE TEST CASES (25-35% of total):**
- Invalid inputs and data
- Error handling verification
- Exception scenarios
- Missing required fields
- Malformed data

**BOUNDARY TEST CASES (15-20% of total):**
- Minimum and maximum values
- Empty/null/zero values
- Length limits
- Threshold conditions

**INTEGRATION TEST CASES (10-15% of total):**
- Component interactions
- API integration points
- Database operations
- External system dependencies

**SECURITY TEST CASES (5-10% of total):**
- Authentication and authorization
- Input validation and sanitization
- SQL injection, XSS prevention
- Access control verification

**PERFORMANCE TEST CASES (5-10% of total):**
- Load handling
- Response time requirements
- Concurrent user scenarios
- Resource utilization

For EACH test case, use this EXACT format (use #### for test case headings):

#### TC_001
**Test Title:** Clear, descriptive title (e.g., "Verify successful login with valid credentials")
**Category:** positive | negative | boundary | integration | security | performance
**Priority:** Critical | High | Medium | Low
**Description:** Detailed description of what this test validates
**Prerequisites:** Any setup required before executing this test
**Test Data:** Specific data values to use (be precise: usernames, passwords, IDs, etc.)
**Test Steps:**
  1. First action to perform
  2. Second action to perform
  3. Continue with all steps...
**Expected Results:** Precise expected outcome for the test
**Postconditions:** System state after test execution

Repeat this format for TC_002, TC_003, etc.

===SECTION 2: TEST PLANNING ANALYSIS===

Provide a brief analysis:
1. Feature Overview: What functionality is being tested
2. Test Objectives: What we're validating
3. Coverage Analysis: Breakdown by category (e.g., "Positive: 6 tests, Negative: 5 tests...")
4. Risk Areas: High-priority areas requiring extra attention

=== FORMAT REQUIREMENTS ===

MANDATORY FORMAT RULES:
1. Start with ===SECTION 1: COMPREHENSIVE TEST CASES===
2. Use #### TC_001, #### TC_002, etc. for each test case heading
3. Follow the exact field structure shown above for every test case
4. Generate at least 15-25 complete test cases before moving to Section 2
5. End test cases with ===SECTION 2: TEST PLANNING ANALYSIS===
6. Be SPECIFIC with test data (no generic "test@example.com" - use realistic data)
7. Make test steps DETAILED and EXECUTABLE
8. Ensure expected results are PRECISE and MEASURABLE
9. Cover ALL edge cases and error scenarios
10. Think like a tester trying to BREAK the system

=== QUALITY STANDARDS ===

Your output will be evaluated on:
- Completeness: Are all scenarios covered?
- Clarity: Can any tester execute these without questions?
- Coverage: Do we test positive, negative, boundary, integration, security, and performance?
- Detail: Are test steps, data, and expected results specific?
- Realism: Are test cases practical and executable?

⚠️ FINAL REMINDER ⚠️
Your response MUST begin with:
===SECTION 1: COMPREHENSIVE TEST CASES===
#### TC_001
**Test Title:** ...

Start generating test cases NOW. Do NOT write any introduction or explanation first."""

        return f"{system_prompt}\n\n{user_instruction}"

    def generate(
        self,
        user_prompt: str,
        output_formats: list = None,
        max_retries: int = 2
    ) -> Dict:
        """
        Generate comprehensive test cases from user prompt

        Args:
            user_prompt: User's feature/requirement description
            output_formats: List of output formats ['json', 'markdown', 'excel']
            max_retries: Number of retries if generation fails

        Returns:
            Dictionary containing test cases and metadata
        """
        logger.info("=" * 80)
        logger.info("STARTING TEST CASE GENERATION")
        logger.info("=" * 80)

        try:
            # Step 1: Prompt Preprocessing
            logger.info("\n[STEP 1] Prompt Preprocessing & Analysis")
            logger.info("-" * 80)

            prompt_analysis = self.prompt_preprocessor.analyze_prompt(user_prompt)

            logger.info(f"Intent: {prompt_analysis['intent']}")
            logger.info(f"Feature: {prompt_analysis['feature_name']}")
            logger.info(f"Keywords: {', '.join(prompt_analysis['keywords'][:5])}")
            logger.info(f"Generated {len(prompt_analysis['search_queries'])} search queries")

            # Step 2: RAG Retrieval
            logger.info("\n[STEP 2] RAG Context Retrieval")
            logger.info("-" * 80)

            rag_results = self.enhanced_retrieval.adaptive_retrieve(
                queries=prompt_analysis['search_queries'],
                min_results=10,
                max_results=20
            )

            logger.info(f"Retrieved {len(rag_results)} relevant context chunks")

            # Log source documents
            sources = set(r.get('file_path', 'Unknown') for r in rag_results)
            logger.info(f"Sources: {len(sources)} unique documents")
            for source in sorted(sources):
                logger.info(f"  - {Path(source).name}")

            # Step 2.5: Domain Expert Enrichment (if available)
            domain_enriched_context = None
            if self.domain_expert and self.domain_expert.concept_graph:
                logger.info("\n[STEP 2.5] Domain Expert Concept Enrichment")
                logger.info("-" * 80)

                try:
                    # Extract text chunks from RAG results for domain expert
                    rag_chunks = [r.get('text', '') for r in rag_results]

                    # Get enriched context from domain expert
                    domain_context = self.domain_expert.get_enriched_context(
                        user_query=user_prompt,
                        rag_chunks=rag_chunks
                    )

                    if domain_context and domain_context.get('primary_concepts'):
                        concepts = domain_context['primary_concepts']
                        logger.info(f"Identified {len(concepts)} primary concepts from domain knowledge")

                        # Build domain-enriched context string
                        domain_parts = []

                        # Add concept hierarchy
                        if domain_context.get('concept_hierarchy'):
                            hierarchy = domain_context['concept_hierarchy']
                            domain_parts.append("=== DOMAIN KNOWLEDGE: HIERARCHICAL CONCEPTS ===\n")
                            for concept_data in hierarchy:
                                concept_name = concept_data.get('name', 'Unknown')
                                domain_parts.append(f"\n**{concept_name}** ({concept_data.get('type', 'concept')})")
                                domain_parts.append(f"Description: {concept_data.get('description', 'N/A')}")

                                if concept_data.get('sub_concepts'):
                                    domain_parts.append(f"Sub-concepts: {', '.join([sc.get('name', '') for sc in concept_data['sub_concepts'][:5]])}")

                                if concept_data.get('test_dimensions'):
                                    domain_parts.append(f"Test Dimensions: {', '.join(concept_data['test_dimensions'])}")

                        # Add test strategy
                        if domain_context.get('test_strategy'):
                            strategy = domain_context['test_strategy']
                            domain_parts.append("\n\n=== DOMAIN KNOWLEDGE: TEST STRATEGY ===")
                            domain_parts.append(f"Focus Areas: {strategy.get('focus_areas', 'N/A')}")
                            domain_parts.append(f"Required Scenarios: {strategy.get('required_scenarios', 'N/A')}")
                            domain_parts.append(f"Priority Concepts: {strategy.get('priority_concepts', 'N/A')}")

                        # Add test scenarios
                        if domain_context.get('test_scenarios'):
                            scenarios = domain_context['test_scenarios']
                            domain_parts.append("\n\n=== DOMAIN KNOWLEDGE: PRE-DEFINED TEST SCENARIOS ===")
                            for i, scenario in enumerate(scenarios[:10], 1):
                                domain_parts.append(f"{i}. {scenario}")

                        domain_enriched_context = "\n".join(domain_parts)
                        logger.info(f"Domain-enriched context: {len(domain_enriched_context)} characters")
                        logger.info(f"Concepts: {', '.join([c.get('name', 'Unknown') for c in concepts[:5]])}")
                    else:
                        logger.info("No relevant concepts found in domain knowledge")

                except Exception as e:
                    logger.warning(f"Domain expert enrichment failed: {e}")
                    domain_enriched_context = None
            else:
                if not self.domain_expert:
                    logger.info("\n[STEP 2.5] Domain Expert not available - skipping concept enrichment")
                else:
                    logger.info("\n[STEP 2.5] Domain knowledge base empty - build domain knowledge first")

            # Step 2.7: PKG Loading (Product Knowledge Graph)
            pkg_context = None
            if self.pkg_loader:
                logger.info("\n[STEP 2.7] PKG Loading (Product Knowledge Graph)")
                logger.info("-" * 80)

                try:
                    # Identify relevant features
                    pkg_data = self.pkg_loader.get_pkgs_for_query(user_prompt)

                    if pkg_data['pkgs']:
                        logger.info(f"Identified {len(pkg_data['features'])} relevant features:")
                        for feat in pkg_data['features']:
                            logger.info(f"  - {feat['feature_name']} ({feat['feature_id']})")

                        # Format PKGs for prompt
                        pkg_parts = []
                        pkg_parts.append("=== PRODUCT KNOWLEDGE GRAPH (PKG) - PRIMARY SOURCE ===\n")
                        pkg_parts.append("The following is structured product knowledge extracted from documentation.")
                        pkg_parts.append("THIS IS YOUR PRIMARY SOURCE. Use EXACT field names, ranges, and constraints from PKG.\n")

                        for feature_id, pkg in pkg_data['pkgs'].items():
                            # Skip malformed PKG entries
                            if not isinstance(pkg, dict):
                                logger.warning(f"Skipping malformed PKG for {feature_id}: expected dict, got {type(pkg).__name__}")
                                continue
                            formatted_pkg = self.pkg_loader.format_pkg_for_prompt(feature_id)
                            pkg_parts.append(formatted_pkg)

                        pkg_context = "\n".join(pkg_parts)

                        # Filter valid PKGs for logging
                        valid_pkgs = [pkg for pkg in pkg_data['pkgs'].values() if isinstance(pkg, dict)]
                        logger.info(f"PKG context: {len(pkg_context)} characters")
                        logger.info(f"Total inputs across features: {sum(len(pkg.get('inputs', [])) for pkg in valid_pkgs)}")
                        logger.info(f"Total constraints: {sum(len(pkg.get('constraints', [])) for pkg in valid_pkgs)}")
                    else:
                        logger.info("No relevant PKG found for this query")

                except Exception as e:
                    logger.warning(f"PKG loading failed: {e}")
                    pkg_context = None
            else:
                logger.info("\n[STEP 2.7] PKG Loader not available - skipping structured product knowledge")

            # Step 3: Context Enrichment
            logger.info("\n[STEP 3] Context Enrichment")
            logger.info("-" * 80)

            enriched_context = self.prompt_preprocessor.enrich_context(
                user_prompt,
                rag_results
            )

            # Merge PKG, Domain Expert, and RAG context (in order of priority)
            final_context_parts = []

            # Priority 1: PKG (most specific, structured product knowledge)
            if pkg_context:
                final_context_parts.append(pkg_context)
                logger.info("✓ PKG context added as PRIMARY source")

            # Priority 2: Domain Expert (hierarchical concepts)
            if domain_enriched_context:
                final_context_parts.append(domain_enriched_context)
                logger.info("✓ Domain knowledge added as SECONDARY source")

            # Priority 3: RAG (general documentation context)
            final_context_parts.append(f"=== RAG RETRIEVED CONTEXT (for additional context) ===\n{enriched_context}")

            enriched_context = "\n\n".join(final_context_parts)
            logger.info(f"Final enriched context: {len(enriched_context)} characters")

            # Step 4: Build Master Prompt
            logger.info("\n[STEP 4] Building Comprehensive Prompt")
            logger.info("-" * 80)

            master_prompt = self._build_master_prompt(user_prompt, enriched_context)
            logger.info(f"Master prompt: {len(master_prompt)} characters")

            # Step 5: Azure OpenAI Generation
            logger.info("\n[STEP 5] Generating Test Cases with Azure OpenAI")
            logger.info("-" * 80)

            for attempt in range(max_retries + 1):
                try:
                    logger.info(f"Generation attempt {attempt + 1}/{max_retries + 1}...")

                    generated_output = self.azure_llm.generate(
                        prompt=master_prompt,
                        temperature=1.0,  # Fixed for GPT-5 compatibility
                        max_tokens=config.LLM_MAX_TOKENS  # Use config value for model switching
                    )

                    logger.info(f"Generated {len(generated_output)} characters")
                    break

                except Exception as e:
                    if attempt < max_retries:
                        logger.warning(f"Generation attempt {attempt + 1} failed: {e}")
                        logger.info("Retrying...")
                        continue
                    else:
                        raise

            # Parse output into sections
            sections = self._parse_output(generated_output)

            # Step 6: Output Formatting
            logger.info("\n[STEP 6] Output Formatting & Export")
            logger.info("-" * 80)

            result = {
                'test_plan': sections.get('planning', ''),
                'test_cases': sections.get('test_cases', ''),
                'validation_report': sections.get('validation', ''),
                'final_output': generated_output,
                'status': 'success'
            }

            output_formats = output_formats or config.OUTPUT_FORMATS
            output_files = {}

            if 'json' in output_formats:
                output_files['json'] = self.formatter.save_as_json(result)

            if 'markdown' in output_formats:
                output_files['markdown'] = self.formatter.save_as_markdown(result)

            if 'excel' in output_formats:
                output_files['excel'] = self.formatter.save_as_excel(result)

            result['output_files'] = output_files
            result['metadata'] = {
                'user_prompt': user_prompt,
                'intent': prompt_analysis['intent'],
                'feature_name': prompt_analysis['feature_name'],
                'sources_count': len(sources),
                'sources': list(sources),
                'rag_results_count': len(rag_results)
            }

            logger.info(f"Test cases saved to {len(output_files)} formats:")
            for fmt, filepath in output_files.items():
                logger.info(f"  - {fmt.upper()}: {filepath}")

            logger.info("\n" + "=" * 80)
            logger.info("TEST CASE GENERATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)

            return result

        except Exception as e:
            logger.error(f"Test case generation failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'test_plan': '',
                'test_cases': '',
                'validation_report': '',
                'final_output': '',
                'output_files': {},
                'metadata': {}
            }

    def _parse_output(self, output: str) -> Dict[str, str]:
        """
        Parse generated output into sections

        Args:
            output: Generated text from Azure OpenAI

        Returns:
            Dictionary with parsed sections
        """
        sections = {
            'planning': '',
            'test_cases': '',
            'validation': ''
        }

        # Parse based on new section order: SECTION 1 = test cases, SECTION 2 = planning
        # Handle both ===SECTION X=== and SECTION X formats
        if '===SECTION 1' in output or 'SECTION 1' in output:
            # Split on SECTION 2 (with or without ===)
            if '===SECTION 2' in output:
                parts = output.split('===SECTION 2')
            elif 'SECTION 2' in output:
                parts = output.split('SECTION 2')
            else:
                parts = [output]

            if len(parts) > 1:
                # Both sections present
                sections['test_cases'] = parts[0].replace('===SECTION 1', '').replace('SECTION 1', '').replace('===', '').strip()
                sections['planning'] = parts[1].replace('===', '').strip()
            else:
                # Only section 1 present
                sections['test_cases'] = parts[0].replace('===SECTION 1', '').replace('SECTION 1', '').replace('===', '').strip()
        elif 'TEST CASE' in output or 'TC_' in output:
            # Fallback: treat entire output as test cases
            sections['test_cases'] = output
        else:
            # Last resort: assume entire output is test cases
            sections['test_cases'] = output

        return sections

    def generate_interactive(self):
        """
        Interactive mode for test case generation
        """
        print("\n" + "=" * 80)
        print("SIMPLIFIED AI-POWERED TEST CASE GENERATOR")
        print("Single Azure OpenAI Call - Fast & Efficient")
        print("=" * 80)
        print()

        # Check vector store
        stats = self.vector_store.get_stats()
        print(f"Knowledge Base: {stats['total_documents']} documents, {stats['total_chunks']} chunks indexed")
        print()

        if stats['total_chunks'] == 0:
            print("[WARNING] No documents indexed in the knowledge base!")
            print("   Please run document ingestion first: python src/main_enterprise.py -> [I]")
            print()
            return

        # Get user input
        print("Enter feature/requirement description:")
        print("(e.g., 'User authentication with OAuth2', 'API endpoint /users/create')")
        print()

        user_prompt = input("Your input: ").strip()

        if not user_prompt:
            print("No input provided. Exiting.")
            return

        print()
        print("=" * 80)
        print("GENERATING TEST CASES...")
        print("=" * 80)

        # Generate
        result = self.generate(
            user_prompt=user_prompt,
            output_formats=['json', 'markdown', 'excel']
        )

        # Display summary
        print("\n" + "=" * 80)
        print("GENERATION SUMMARY")
        print("=" * 80)

        if result['status'] == 'success':
            print(f"[OK] Status: SUCCESS")
            print(f"[OK] Sources: {result['metadata']['sources_count']} documents")
            print(f"[OK] Context: {result['metadata']['rag_results_count']} chunks")
            print()
            print("Output files:")
            for fmt, filepath in result['output_files'].items():
                print(f"  - {fmt.upper()}: {filepath}")
            print()
            print("[SUCCESS] Test cases generated successfully!")
        else:
            print(f"[ERROR] Status: FAILED")
            print(f"[ERROR] Error: {result.get('error', 'Unknown error')}")

        print("=" * 80)


def main():
    """Main entry point"""
    generator = SimpleTestGenerator()
    generator.generate_interactive()


if __name__ == "__main__":
    main()
