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

logger = setup_logger(__name__)


class SimpleTestGenerator:
    """
    Simplified AI-Powered Test Case Generator
    Uses single optimized Azure OpenAI call instead of multi-agent orchestration
    """

    def __init__(self):
        """Initialize test case generator"""
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

        user_instruction = f"""Based on the documentation context provided below, generate a COMPREHENSIVE set of test cases for the following requirement:

=== USER REQUIREMENT ===
{user_prompt}

=== DOCUMENTATION CONTEXT (Retrieved from Knowledge Base) ===
{rag_context}

=== YOUR TASK ===

CRITICAL: You MUST generate the test cases in SECTION 1 first. Do NOT start with analysis - generate the actual test cases immediately.

Your output must include:

**SECTION 1: COMPREHENSIVE TEST CASES (GENERATE THIS FIRST)**

Generate at least 15 test cases distributed across these categories:

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

For EACH test case, provide ALL of the following fields:

**Test ID:** TC_XXX (sequential numbering: TC_001, TC_002, etc.)
**Test Title:** Clear, descriptive title (e.g., "Verify successful login with valid credentials")
**Category:** positive | negative | boundary | integration | security | performance
**Priority:** Critical | High | Medium | Low
**Description:** Detailed description of what this test validates
**Prerequisites:** Any setup required before executing this test
**Test Data:** Specific data values to use (be precise: usernames, passwords, IDs, etc.)
**Test Steps:** Numbered step-by-step execution instructions
  1. First action to perform
  2. Second action to perform
  3. Continue with all steps...
**Expected Results:** Precise expected outcome for the test
**Postconditions:** System state after test execution

**SECTION 2: TEST PLANNING ANALYSIS (Brief overview AFTER test cases)**

Provide a brief analysis:
1. Feature Overview: What functionality is being tested
2. Test Objectives: What we're validating
3. Coverage Analysis: Breakdown by category (e.g., "Positive: 6 tests, Negative: 5 tests...")
4. Risk Areas: High-priority areas requiring extra attention

=== FORMAT REQUIREMENTS ===

- Use clear section headers with === markers
- Number all test cases sequentially (TC_001, TC_002, etc.)
- Be SPECIFIC with test data (no generic "test@example.com" - use realistic data)
- Make test steps DETAILED and EXECUTABLE
- Ensure expected results are PRECISE and MEASURABLE
- Cover ALL edge cases and error scenarios
- Think like a tester trying to BREAK the system

=== QUALITY STANDARDS ===

Your output will be evaluated on:
- Completeness: Are all scenarios covered?
- Clarity: Can any tester execute these without questions?
- Coverage: Do we test positive, negative, boundary, integration, security, and performance?
- Detail: Are test steps, data, and expected results specific?
- Realism: Are test cases practical and executable?

Generate the comprehensive test suite now."""

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

            # Step 3: Context Enrichment
            logger.info("\n[STEP 3] Context Enrichment")
            logger.info("-" * 80)

            enriched_context = self.prompt_preprocessor.enrich_context(
                user_prompt,
                rag_results
            )

            logger.info(f"Enriched context: {len(enriched_context)} characters")

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
                        temperature=0.7,  # Balanced creativity
                        max_tokens=8000   # Increased for comprehensive test cases
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
        if 'SECTION 1' in output:
            parts = output.split('SECTION 2')
            if len(parts) > 1:
                sections['test_cases'] = parts[0].replace('SECTION 1', '').strip()
                sections['planning'] = parts[1].strip()
            else:
                # Only section 1 present
                sections['test_cases'] = parts[0].replace('SECTION 1', '').strip()
        elif 'TEST CASE' in output or 'TC_' in output:
            # Fallback: treat entire output as test cases
            sections['test_cases'] = output
        else:
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
