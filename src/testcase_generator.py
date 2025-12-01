"""
AI-Powered Test Case Generator
Main workflow: User Prompt → RAG Retrieval → CrewAI Orchestration → Test Cases
"""
import sys
from pathlib import Path
from typing import Dict, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import config
from src.utils.logger import setup_logger
from src.utils.prompt_preprocessor import PromptPreprocessor
from src.utils.output_formatter import TestCaseFormatter
from src.vector_db.vector_store import VectorStore
from src.vector_db.search_engine import HybridSearchEngine
from src.vector_db.enhanced_retrieval import EnhancedRetrieval
from src.orchestration.crew_orchestrator import CrewOrchestrator

logger = setup_logger(__name__)


class TestCaseGenerator:
    """
    AI-Powered Test Case Generator
    Integrates RAG + CrewAI for comprehensive test case generation
    """

    def __init__(self):
        """Initialize test case generator"""
        logger.info("=" * 80)
        logger.info("Initializing AI-Powered Test Case Generator")
        logger.info("=" * 80)

        # Initialize components
        logger.info("Loading RAG components...")
        self.vector_store = VectorStore()
        self.search_engine = HybridSearchEngine(self.vector_store)
        self.enhanced_retrieval = EnhancedRetrieval(self.search_engine)

        logger.info("Loading AI components...")
        self.prompt_preprocessor = PromptPreprocessor()
        self.crew_orchestrator = CrewOrchestrator()
        self.formatter = TestCaseFormatter()

        logger.info("=" * 80)
        logger.info("Test Case Generator initialized successfully")
        logger.info("=" * 80)

    def generate(
        self,
        user_prompt: str,
        output_formats: list = None,
        use_iteration: bool = False
    ) -> Dict:
        """
        Generate comprehensive test cases from user prompt

        Workflow:
        1. Prompt Preprocessing: Analyze user prompt and extract key information
        2. RAG Retrieval: Retrieve relevant documentation using multi-query optimization
        3. Context Enrichment: Combine user prompt + RAG results
        4. CrewAI Orchestration: Execute multi-agent workflow
        5. Output Formatting: Export in multiple formats

        Args:
            user_prompt: User's feature/requirement description
            output_formats: List of output formats ['json', 'markdown', 'excel']
            use_iteration: Enable iterative refinement

        Returns:
            Dictionary containing:
                - test_plan: Test planning analysis
                - test_cases: Generated test cases
                - validation_report: Quality validation report
                - output_files: Paths to saved files
                - metadata: Generation metadata
        """
        logger.info("=" * 80)
        logger.info("STARTING TEST CASE GENERATION WORKFLOW")
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

            # Step 4: CrewAI Orchestration
            logger.info("\n[STEP 4] CrewAI Multi-Agent Orchestration")
            logger.info("-" * 80)

            if use_iteration:
                logger.info("Using iterative refinement mode")
                result = self.crew_orchestrator.generate_with_iteration(enriched_context)
            else:
                logger.info("Using single-pass generation mode")
                result = self.crew_orchestrator.generate_test_cases(enriched_context)

            if result['status'] == 'error':
                logger.error(f"Test case generation failed: {result.get('error')}")
                return result

            # Step 5: Output Formatting
            logger.info("\n[STEP 5] Output Formatting & Export")
            logger.info("-" * 80)

            output_formats = output_formats or config.OUTPUT_FORMATS
            output_files = {}

            if 'json' in output_formats:
                output_files['json'] = self.formatter.save_as_json(result)

            if 'markdown' in output_formats:
                output_files['markdown'] = self.formatter.save_as_markdown(result)

            if 'excel' in output_formats:
                output_files['excel'] = self.formatter.save_as_excel(result)

            # Add output files and metadata to result
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
                'output_files': {},
                'metadata': {}
            }

    def generate_interactive(self):
        """
        Interactive mode for test case generation

        Prompts user for input and generates test cases
        """
        print("\n" + "=" * 80)
        print("AI-POWERED TEST CASE GENERATOR")
        print("Powered by RAG + Azure OpenAI + CrewAI Multi-Agent System")
        print("=" * 80)
        print()

        # Check vector store
        stats = self.vector_store.get_stats()
        print(f"Knowledge Base: {stats['total_documents']} documents, {stats['total_chunks']} chunks indexed")
        print()

        if stats['total_chunks'] == 0:
            print("⚠️  WARNING: No documents indexed in the knowledge base!")
            print("   Please run document ingestion first: [I] Ingest documents")
            print()
            return

        # Get user input
        print("Enter feature/requirement description:")
        print("(Can be a feature name, API endpoint, workflow, or any test requirement)")
        print()

        user_prompt = input("Your input: ").strip()

        if not user_prompt:
            print("No input provided. Exiting.")
            return

        print()
        print("=" * 80)
        print("GENERATING TEST CASES...")
        print("=" * 80)

        # Options
        print("\nOptions:")
        use_iteration = input("Use iterative refinement? (y/n) [n]: ").strip().lower() == 'y'

        # Generate
        result = self.generate(
            user_prompt=user_prompt,
            output_formats=['json', 'markdown', 'excel'],
            use_iteration=use_iteration
        )

        # Display summary
        print("\n" + "=" * 80)
        print("GENERATION SUMMARY")
        print("=" * 80)

        if result['status'] == 'success':
            print(f"✓ Status: SUCCESS")
            print(f"✓ Sources: {result['metadata']['sources_count']} documents")
            print(f"✓ Context: {result['metadata']['rag_results_count']} chunks")
            print()
            print("Output files:")
            for fmt, filepath in result['output_files'].items():
                print(f"  • {fmt.upper()}: {filepath}")
            print()
            print("Test cases generated successfully!")
        else:
            print(f"✗ Status: FAILED")
            print(f"✗ Error: {result.get('error', 'Unknown error')}")

        print("=" * 80)


def main():
    """Main entry point"""
    generator = TestCaseGenerator()
    generator.generate_interactive()


if __name__ == "__main__":
    main()
