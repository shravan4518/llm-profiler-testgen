"""
Task Planner Agent
Analyzes feature requirements and plans comprehensive test coverage
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


def create_task_planner_agent(llm) -> Agent:
    """
    Create Task Planner Agent

    Args:
        llm: LangChain LLM instance

    Returns:
        CrewAI Agent for task planning
    """

    agent = Agent(
        role='Senior QA Test Architect',
        goal='Analyze feature requirements and create comprehensive test planning strategy',
        backstory="""You are a senior QA architect with 15+ years of experience in enterprise
        software testing. You excel at analyzing feature requirements and identifying all possible
        test scenarios for maximum coverage. You understand:
        - Positive and negative test cases
        - Boundary value analysis
        - Integration testing requirements
        - Security and performance testing needs
        - Edge cases and error handling
        - Regression testing impact

        You create thorough test plans that ensure 95%+ code coverage.""",
        verbose=config.AGENT_VERBOSE,
        allow_delegation=False,
        llm=llm
    )

    logger.info("Task Planner Agent created")
    return agent


def create_planning_task(agent: Agent, context: str) -> Task:
    """
    Create planning task for the agent

    Args:
        agent: Task Planner Agent
        context: Enriched context from RAG

    Returns:
        CrewAI Task
    """

    task = Task(
        description=f"""Based on the following context, analyze the feature/functionality
        and create a comprehensive test planning strategy.

        {context}

        Your analysis must include:
        1. Feature Overview (what needs to be tested)
        2. Test Objectives (what we're validating)
        3. Test Coverage Areas:
           - Positive scenarios (happy path)
           - Negative scenarios (error cases)
           - Boundary conditions
           - Integration points
           - Security considerations
           - Performance requirements
           - Edge cases
        4. Risk Areas (high-risk functionality)
        5. Prerequisites and Dependencies
        6. Test Data Requirements

        Provide a detailed analysis in structured format.""",
        agent=agent,
        expected_output="""Comprehensive test plan with:
        - Feature overview
        - Test objectives
        - Coverage areas (positive, negative, boundary, integration, security, performance)
        - Risk areas
        - Prerequisites
        - Test data requirements"""
    )

    return task
