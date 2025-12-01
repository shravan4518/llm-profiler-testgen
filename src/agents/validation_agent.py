"""
Validation Agent
Validates test cases for quality, coverage, and completeness
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import config
from src.utils.logger import setup_logger
from crewai import Agent, Task

logger = setup_logger(__name__)


def create_validation_agent(llm) -> Agent:
    """
    Create Validation Agent

    Args:
        llm: LangChain LLM instance

    Returns:
        CrewAI Agent for validation
    """

    agent = Agent(
        role='Senior QA Quality Auditor',
        goal='Validate test cases for completeness, coverage, and quality standards',
        backstory="""You are a meticulous QA quality auditor with expertise in test case review
        and quality assurance standards. You have reviewed thousands of test suites and can
        quickly identify gaps, ambiguities, and quality issues.

        You validate test cases against strict criteria:
        - Completeness (all fields present and detailed)
        - Coverage (all scenarios covered: positive, negative, boundary, etc.)
        - Clarity (unambiguous, executable by anyone)
        - Traceability (linked to requirements)
        - Independence (tests don't depend on each other)
        - Consistency (similar format and detail level)
        - Standards compliance (IEEE 829, ISO/IEC/IEEE 29119)

        You identify:
        - Missing test scenarios
        - Ambiguous test steps
        - Incomplete expected results
        - Missing edge cases
        - Coverage gaps
        - Quality issues

        You provide actionable feedback to improve test suites to enterprise-grade quality.""",
        verbose=config.AGENT_VERBOSE,
        allow_delegation=False,
        llm=llm
    )

    logger.info("Validation Agent created")
    return agent


def create_validation_task(agent: Agent, test_cases: str, planning: str) -> Task:
    """
    Create validation task

    Args:
        agent: Validation Agent
        test_cases: Generated test cases
        planning: Original test planning

    Returns:
        CrewAI Task
    """

    task = Task(
        description=f"""Review and validate the generated test cases against the test plan
        and quality standards.

        TEST PLANNING STRATEGY:
        {planning}

        GENERATED TEST CASES:
        {test_cases}

        Validate the test cases and provide:

        1. COVERAGE ANALYSIS:
           - Positive scenarios coverage: X/X complete
           - Negative scenarios coverage: X/X complete
           - Boundary scenarios coverage: X/X complete
           - Integration scenarios coverage: X/X complete
           - Security scenarios coverage: X/X complete
           - Performance scenarios coverage: X/X complete

        2. QUALITY CHECK:
           - All fields present and complete? (Yes/No)
           - Test steps clear and executable? (Yes/No)
           - Expected results precise? (Yes/No)
           - Test data specified? (Yes/No)
           - Independent and repeatable? (Yes/No)

        3. GAP ANALYSIS:
           - Missing scenarios (list them)
           - Ambiguous test cases (identify which ones)
           - Edge cases not covered (list them)

        4. RECOMMENDATIONS:
           - Additional test cases needed
           - Test cases to improve
           - Coverage enhancements

        5. FINAL VERDICT:
           - Overall quality score (1-10)
           - Ready for execution? (Yes/No/With modifications)
           - Summary assessment

        If test cases are not comprehensive enough, suggest specific additional test cases needed.""",
        agent=agent,
        expected_output="""Comprehensive validation report with:
        - Coverage analysis for all coverage types
        - Quality assessment
        - Gap analysis
        - Recommendations for improvement
        - Final verdict with quality score
        - Specific suggestions for missing test cases"""
    )

    return task
