"""
Test Case Generator Agent
Generates comprehensive, detailed test cases from test plans
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


def create_test_generator_agent(llm) -> Agent:
    """
    Create Test Case Generator Agent

    Args:
        llm: LangChain LLM instance

    Returns:
        CrewAI Agent for test case generation
    """

    agent = Agent(
        role='Expert Test Case Designer',
        goal='Generate detailed, executable test cases with maximum coverage',
        backstory="""You are an expert test case designer with deep knowledge of test automation
        frameworks, enterprise software testing, and quality assurance best practices.

        You excel at:
        - Writing clear, unambiguous test cases
        - Creating detailed test steps
        - Defining precise expected results
        - Identifying test data requirements
        - Categorizing tests appropriately (smoke, regression, integration)
        - Ensuring traceability to requirements
        - Writing test cases that are automation-ready

        You follow industry standards (IEEE 829, ISO/IEC/IEEE 29119) and ensure every test case
        has: Test ID, Title, Description, Prerequisites, Test Steps, Expected Results, Test Data,
        Priority, and Category.

        Your test cases are so detailed that any tester can execute them without ambiguity.""",
        verbose=config.AGENT_VERBOSE,
        allow_delegation=False,
        llm=llm
    )

    logger.info("Test Generator Agent created")
    return agent


def create_generation_task(agent: Agent, planning_output: str, context: str) -> Task:
    """
    Create test generation task

    Args:
        agent: Test Generator Agent
        planning_output: Output from task planner
        context: Original RAG context

    Returns:
        CrewAI Task
    """

    task = Task(
        description=f"""Based on the test planning strategy and documentation context,
        generate comprehensive, detailed test cases.

        TEST PLANNING STRATEGY:
        {planning_output}

        DOCUMENTATION CONTEXT:
        {context}

        Generate at least {config.MIN_TEST_CASES_PER_FEATURE} test cases covering ALL aspects:

        For EACH test case, provide:
        1. Test ID: Unique identifier (e.g., TC_001, TC_002)
        2. Test Title: Clear, descriptive title
        3. Category: {', '.join(config.COVERAGE_TYPES)}
        4. Priority: Critical/High/Medium/Low
        5. Description: What this test validates
        6. Prerequisites: Setup required before test
        7. Test Data: Specific data needed
        8. Test Steps: Detailed step-by-step execution (numbered)
        9. Expected Results: Precise expected outcome for each step
        10. Postconditions: State after test execution

        COVERAGE REQUIREMENTS:
        - Positive test cases (happy path scenarios)
        - Negative test cases (error handling, invalid inputs)
        - Boundary test cases (min/max values, limits)
        - Integration test cases (component interactions)
        - Security test cases (authentication, authorization, input validation)
        - Performance test cases (if applicable)

        Format each test case clearly and ensure they are:
        - Specific and unambiguous
        - Executable by any tester
        - Traceable to requirements
        - Independent of each other
        - Repeatable

        Generate comprehensive test cases now.""",
        agent=agent,
        expected_output=f"""Minimum {config.MIN_TEST_CASES_PER_FEATURE} detailed test cases, each containing:
        - Test ID
        - Test Title
        - Category (positive/negative/boundary/integration/security/performance)
        - Priority
        - Description
        - Prerequisites
        - Test Data
        - Test Steps (numbered)
        - Expected Results
        - Postconditions

        Test cases must cover all coverage types and provide maximum feature coverage."""
    )

    return task
