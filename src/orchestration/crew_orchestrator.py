"""
CrewAI Orchestration Layer
Coordinates multi-agent workflow for test case generation
"""
import sys
from pathlib import Path
from typing import Dict, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import config
from src.utils.logger import setup_logger
from src.utils.azure_llm import get_azure_llm
from src.agents.task_planner_agent import create_task_planner_agent, create_planning_task
from src.agents.test_generator_agent import create_test_generator_agent, create_generation_task
from src.agents.validation_agent import create_validation_agent, create_validation_task
from crewai import Crew, Process

logger = setup_logger(__name__)


class CrewOrchestrator:
    """
    Orchestrates multi-agent workflow for comprehensive test case generation
    """

    def __init__(self):
        """Initialize CrewAI orchestrator"""
        logger.info("Initializing CrewAI Orchestrator...")

        # Get Azure LLM
        self.azure_llm = get_azure_llm()
        self.llm = self.azure_llm.get_langchain_llm()

        # Create agents
        self.task_planner = create_task_planner_agent(self.llm)
        self.test_generator = create_test_generator_agent(self.llm)
        self.validator = create_validation_agent(self.llm)

        logger.info("CrewAI Orchestrator initialized with 3 agents")

    def generate_test_cases(self, enriched_context: str) -> Dict:
        """
        Execute multi-agent workflow to generate test cases

        Args:
            enriched_context: Enriched context from RAG + user prompt

        Returns:
            Dictionary containing:
                - test_plan: Planning analysis
                - test_cases: Generated test cases
                - validation_report: Validation assessment
                - final_output: Formatted final output
        """
        logger.info("Starting CrewAI test case generation workflow...")

        try:
            # Phase 1: Planning
            logger.info("Phase 1: Test Planning...")
            planning_task = create_planning_task(self.task_planner, enriched_context)

            planning_crew = Crew(
                agents=[self.task_planner],
                tasks=[planning_task],
                process=Process.sequential,
                verbose=config.AGENT_VERBOSE
            )

            planning_output = planning_crew.kickoff()
            test_plan = str(planning_output)
            logger.info(f"Planning complete: {len(test_plan)} characters")

            # Phase 2: Test Case Generation
            logger.info("Phase 2: Test Case Generation...")
            generation_task = create_generation_task(
                self.test_generator,
                test_plan,
                enriched_context
            )

            generation_crew = Crew(
                agents=[self.test_generator],
                tasks=[generation_task],
                process=Process.sequential,
                verbose=config.AGENT_VERBOSE
            )

            generation_output = generation_crew.kickoff()
            test_cases = str(generation_output)
            logger.info(f"Test cases generated: {len(test_cases)} characters")

            # Phase 3: Validation
            logger.info("Phase 3: Validation...")
            validation_task = create_validation_task(
                self.validator,
                test_cases,
                test_plan
            )

            validation_crew = Crew(
                agents=[self.validator],
                tasks=[validation_task],
                process=Process.sequential,
                verbose=config.AGENT_VERBOSE
            )

            validation_output = validation_crew.kickoff()
            validation_report = str(validation_output)
            logger.info(f"Validation complete: {len(validation_report)} characters")

            # Compile final output
            final_output = self._compile_final_output(
                test_plan,
                test_cases,
                validation_report
            )

            logger.info("CrewAI workflow completed successfully")

            return {
                'test_plan': test_plan,
                'test_cases': test_cases,
                'validation_report': validation_report,
                'final_output': final_output,
                'status': 'success'
            }

        except Exception as e:
            logger.error(f"CrewAI workflow failed: {e}")
            return {
                'test_plan': '',
                'test_cases': '',
                'validation_report': '',
                'final_output': f"Error: {str(e)}",
                'status': 'error',
                'error': str(e)
            }

    def _compile_final_output(
        self,
        test_plan: str,
        test_cases: str,
        validation_report: str
    ) -> str:
        """
        Compile final formatted output

        Args:
            test_plan: Planning output
            test_cases: Generated test cases
            validation_report: Validation report

        Returns:
            Formatted final output
        """
        output_parts = [
            "=" * 80,
            "COMPREHENSIVE TEST CASE GENERATION REPORT",
            "Generated by AI-Powered RAG + CrewAI Multi-Agent System",
            "=" * 80,
            "",
            "=" * 80,
            "1. TEST PLANNING ANALYSIS",
            "=" * 80,
            test_plan,
            "",
            "=" * 80,
            "2. GENERATED TEST CASES",
            "=" * 80,
            test_cases,
            "",
            "=" * 80,
            "3. VALIDATION REPORT",
            "=" * 80,
            validation_report,
            "",
            "=" * 80,
            "END OF REPORT",
            "=" * 80
        ]

        return '\n'.join(output_parts)

    def generate_with_iteration(
        self,
        enriched_context: str,
        max_iterations: int = None
    ) -> Dict:
        """
        Generate test cases with iterative improvement based on validation feedback

        Args:
            enriched_context: Enriched context from RAG
            max_iterations: Maximum iterations (default from config)

        Returns:
            Final test case generation result
        """
        max_iter = max_iterations or config.MAX_ITERATIONS
        logger.info(f"Starting iterative generation (max {max_iter} iterations)...")

        result = None
        iteration = 1

        while iteration <= max_iter:
            logger.info(f"Iteration {iteration}/{max_iter}")

            # Generate test cases
            result = self.generate_test_cases(enriched_context)

            if result['status'] == 'error':
                logger.error("Generation failed, stopping iterations")
                break

            # Check validation report for quality score
            validation = result['validation_report']

            # Simple check: look for quality score or "Ready for execution"
            if "Ready for execution? Yes" in validation or "quality score (10)" in validation.lower():
                logger.info(f"High quality achieved in iteration {iteration}")
                break

            # If not last iteration, continue
            if iteration < max_iter:
                logger.info("Quality not optimal, refining in next iteration...")
                # Add validation feedback to context for next iteration
                enriched_context += f"\n\nPREVIOUS ITERATION FEEDBACK:\n{validation}"

            iteration += 1

        logger.info(f"Iterative generation complete after {iteration} iterations")
        return result
