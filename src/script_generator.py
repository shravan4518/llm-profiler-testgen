"""
Script Generator for Test Cases
Generates Playwright-based automated test scripts using GPT-5 Codex
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from openai import AzureOpenAI

from config import (
    CODEX_ENDPOINT,
    CODEX_API_KEY,
    CODEX_DEPLOYMENT,
    CODEX_API_VERSION,
    SCRIPT_MAX_TOKENS,
    SCRIPT_TEMPERATURE,
    DATA_DIR
)
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ScriptGenerator:
    """Generate automated test scripts from test cases"""

    def __init__(self, rag_system=None):
        """
        Initialize Script Generator

        Args:
            rag_system: RAG system instance for retrieving framework code
        """
        self.rag_system = rag_system

        # Try to use Codex endpoint, fallback to regular Azure OpenAI
        try:
            self.client = AzureOpenAI(
                azure_endpoint=CODEX_ENDPOINT,
                api_key=CODEX_API_KEY,
                api_version=CODEX_API_VERSION
            )
            self.deployment = CODEX_DEPLOYMENT
            logger.info(f"ScriptGenerator initialized with Codex deployment: {self.deployment}")
        except Exception as e:
            logger.warning(f"Could not initialize Codex client: {str(e)}. Using default Azure OpenAI.")
            # Fallback to regular Azure OpenAI
            from config import AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION, AZURE_OPENAI_DEPLOYMENT
            self.client = AzureOpenAI(
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_API_KEY,
                api_version=AZURE_OPENAI_API_VERSION
            )
            self.deployment = AZURE_OPENAI_DEPLOYMENT
            logger.info(f"ScriptGenerator using fallback deployment: {self.deployment}")

    def generate_scripts(
        self,
        job_id: str,
        test_cases: str,
        target_config: Dict,
        user_prompt: str
    ) -> Dict:
        """
        Generate test scripts for a job

        Args:
            job_id: Job identifier
            test_cases: Test cases text
            target_config: Target system configuration
            user_prompt: Original user prompt/feature description

        Returns:
            Result dictionary with script files and status
        """
        try:
            logger.info(f"Generating scripts for job {job_id}")

            # Create job scripts directory
            scripts_dir = Path(DATA_DIR) / 'jobs' / job_id / 'scripts'
            scripts_dir.mkdir(parents=True, exist_ok=True)

            # Parse test cases
            test_cases_list = self._parse_test_cases(test_cases)
            logger.info(f"Parsed {len(test_cases_list)} test cases")

            # Get framework code from RAG
            framework_code = self._retrieve_framework_code(user_prompt, test_cases_list)

            # Generate configuration script
            config_script = self._generate_config_script(
                target_config,
                test_cases_list,
                framework_code
            )

            # Save configuration script
            config_file = scripts_dir / 'conftest.py'
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(config_script)

            # Generate individual test scripts
            test_files = {}
            for i, test_case in enumerate(test_cases_list):
                test_script = self._generate_test_script(
                    test_case,
                    target_config,
                    framework_code,
                    i + 1
                )

                # Save test script
                test_file = scripts_dir / f"test_{test_case['id'].lower()}.py"
                with open(test_file, 'w', encoding='utf-8') as f:
                    f.write(test_script)

                test_files[test_case['id']] = str(test_file)

            # Generate requirements.txt
            requirements_content = self._generate_requirements()
            requirements_file = scripts_dir / 'requirements.txt'
            with open(requirements_file, 'w', encoding='utf-8') as f:
                f.write(requirements_content)

            # Generate README
            readme_content = self._generate_readme(
                job_id,
                test_cases_list,
                target_config
            )
            readme_file = scripts_dir / 'README.md'
            with open(readme_file, 'w', encoding='utf-8') as f:
                f.write(readme_content)

            logger.info(f"Successfully generated {len(test_files)} test scripts")

            return {
                'status': 'success',
                'scripts_dir': str(scripts_dir),
                'config_file': str(config_file),
                'test_files': test_files,
                'requirements_file': str(requirements_file),
                'readme_file': str(readme_file),
                'test_count': len(test_files)
            }

        except Exception as e:
            logger.error(f"Error generating scripts for job {job_id}: {str(e)}")
            return {
                'status': 'failed',
                'error': str(e)
            }

    def _parse_test_cases(self, test_cases_text: str) -> List[Dict]:
        """Parse test cases from text format - supports both #### TC_XXX and **TC_XXX** formats"""
        import re
        test_cases = []

        # Try to match #### TC_XXX format (markdown heading) first
        pattern_heading = r'####\s*TC_\d+'
        pattern_bold = r'\*\*TC_\d+\*\*'

        # Check which format is used
        test_ids_heading = re.findall(pattern_heading, test_cases_text)
        test_ids_bold = re.findall(pattern_bold, test_cases_text)

        if test_ids_heading:
            # Use markdown heading format
            pattern = pattern_heading
            blocks = re.split(pattern, test_cases_text)
            test_ids = [re.search(r'TC_\d+', tid).group() for tid in test_ids_heading]
        elif test_ids_bold:
            # Use bold format
            pattern = pattern_bold
            blocks = re.split(pattern, test_cases_text)
            test_ids = [tid.replace('**', '').strip() for tid in test_ids_bold]
        else:
            logger.warning("No test cases found in expected format")
            return []

        for idx, block in enumerate(blocks[1:]):  # Skip first empty block
            if not block.strip():
                continue

            tc_id = test_ids[idx] if idx < len(test_ids) else f"TC_{idx+1:03d}"

            # Extract test case fields
            tc = {
                'id': tc_id,
                'title': self._extract_field(block, 'Test Title'),
                'category': self._extract_field(block, 'Category'),
                'priority': self._extract_field(block, 'Priority'),
                'description': self._extract_field(block, 'Description'),
                'prerequisites': self._extract_field(block, 'Prerequisites'),
                'test_steps': self._extract_field(block, 'Test Steps'),
                'expected_results': self._extract_field(block, 'Expected Results'),
                'postconditions': self._extract_field(block, 'Postconditions')
            }

            test_cases.append(tc)

        return test_cases

    def _extract_field(self, text: str, field_name: str) -> str:
        """Extract a field value from test case text"""
        import re
        pattern = rf'\*\*{field_name}:\*\*\s*(.*?)(?=\*\*|$)'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ''

    def _retrieve_framework_code(self, query: str, test_cases: List[Dict]) -> str:
        """Retrieve relevant framework code using RAG"""
        if not self.rag_system:
            logger.info("No RAG system available, will use standard Playwright API")
            return ""

        try:
            # Build query from test cases
            queries = [
                "login authentication",
                "logout session management",
                "navigate page navigation",
                "click button interaction",
                "fill form input",
                query  # Include original user prompt
            ]

            framework_snippets = []
            for q in queries:
                # Use the correct method name: 'search' instead of 'query'
                results = self.rag_system.search(
                    query=q,
                    k=3,
                    search_mode='hybrid'
                )

                for result in results:
                    # SearchResult objects have 'score' and 'content' attributes
                    if hasattr(result, 'score') and result.score > 0.5:
                        framework_snippets.append(result.content)
                    elif isinstance(result, dict) and result.get('score', 0) > 0.5:
                        framework_snippets.append(result.get('content', ''))

            logger.info(f"Retrieved {len(framework_snippets)} framework code snippets")
            return "\n\n".join(framework_snippets) if framework_snippets else ""

        except Exception as e:
            logger.warning(f"Could not retrieve framework code: {str(e)}. Will use standard Playwright API.")
            return ""

    def _generate_config_script(
        self,
        target_config: Dict,
        test_cases: List[Dict],
        framework_code: str
    ) -> str:
        """Generate pytest configuration script (conftest.py)"""

        prompt = f"""Generate a comprehensive pytest conftest.py file for Playwright-based test automation.

TARGET SYSTEM:
- URL: {target_config.get('url', 'https://example.com')}
- Username: {target_config.get('username', 'admin')}
- Password: [SECURED]
- Browser: {target_config.get('browser', 'chromium')}
- Environment: {target_config.get('environment', 'dev')}

REQUIREMENTS:
1. Create pytest fixtures for:
   - Browser instance (Playwright {target_config.get('browser', 'chromium')})
   - Authenticated page (login once, reuse session)
   - Test data management
   - Screenshot on failure

2. Configuration:
   - Use Playwright's async API
   - Headless mode by default
   - Viewport size: 1920x1080
   - Timeout: 30 seconds
   - Screenshots on failure

3. Framework code available (if any):
{framework_code[:1000] if framework_code else "No framework code available - use standard Playwright"}

4. Include:
   - Base URL fixture
   - Authentication fixture
   - Cleanup fixtures
   - Logging setup

Generate a production-ready conftest.py file with comprehensive error handling and logging.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are an expert test automation engineer specializing in Python, Playwright, and pytest. Generate clean, production-ready code with proper error handling."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=SCRIPT_MAX_TOKENS,
                temperature=SCRIPT_TEMPERATURE
            )

            script = response.choices[0].message.content

            # Extract code from markdown if present
            if '```python' in script:
                script = script.split('```python')[1].split('```')[0].strip()
            elif '```' in script:
                script = script.split('```')[1].split('```')[0].strip()

            return script

        except Exception as e:
            logger.error(f"Error generating config script: {str(e)}")
            raise Exception(f"Failed to generate configuration script: {str(e)}")

    def _generate_test_script(
        self,
        test_case: Dict,
        target_config: Dict,
        framework_code: str,
        test_number: int
    ) -> str:
        """Generate individual test script"""

        prompt = f"""Generate a Playwright pytest test script for the following test case:

TEST CASE: {test_case['id']}
Title: {test_case['title']}
Category: {test_case['category']}
Priority: {test_case['priority']}

Description:
{test_case['description']}

Prerequisites:
{test_case['prerequisites']}

Test Steps:
{test_case['test_steps']}

Expected Results:
{test_case['expected_results']}

Postconditions:
{test_case['postconditions']}

TARGET SYSTEM:
- URL: {target_config.get('url', 'https://example.com')}
- Browser: {target_config.get('browser', 'chromium')}

FRAMEWORK CODE (use if relevant):
{framework_code[:1000] if framework_code else "Use standard Playwright API"}

REQUIREMENTS:
1. Use pytest and Playwright async API
2. Use fixtures from conftest.py (authenticated_page, browser)
3. Implement each test step clearly with comments
4. Add assertions for expected results
5. Handle errors gracefully
6. Use descriptive variable names
7. Follow PEP 8 style guide

Generate a complete, executable test function. Include docstring and proper async/await syntax.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are an expert test automation engineer. Generate clean, executable Playwright test code with proper error handling and assertions."},
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=SCRIPT_MAX_TOKENS,
                temperature=SCRIPT_TEMPERATURE
            )

            script = response.choices[0].message.content

            # Extract code from markdown if present
            if '```python' in script:
                script = script.split('```python')[1].split('```')[0].strip()
            elif '```' in script:
                script = script.split('```')[1].split('```')[0].strip()

            return script

        except Exception as e:
            logger.error(f"Error generating test script for {test_case['id']}: {str(e)}")
            raise Exception(f"Failed to generate test script for {test_case['id']}: {str(e)}")

    def _generate_requirements(self) -> str:
        """Generate requirements.txt for test execution"""
        return """# Test Automation Dependencies
pytest==7.4.3
pytest-asyncio==0.21.1
playwright==1.40.0
pytest-html==4.1.1
pytest-xdist==3.5.0

# Install Playwright browsers after installing requirements:
# playwright install chromium
"""

    def _generate_readme(
        self,
        job_id: str,
        test_cases: List[Dict],
        target_config: Dict
    ) -> str:
        """Generate README for the test scripts"""
        return f"""# Test Automation Scripts - Job {job_id}

## Overview
This directory contains automated test scripts generated for testing {target_config.get('url', 'the target system')}.

**Total Test Cases**: {len(test_cases)}
**Target Environment**: {target_config.get('environment', 'N/A')}
**Browser**: {target_config.get('browser', 'chromium')}

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install {target_config.get('browser', 'chromium')}
```

## Running Tests

### Run all tests:
```bash
pytest
```

### Run specific test:
```bash
pytest test_tc_001.py
```

### Run with HTML report:
```bash
pytest --html=report.html
```

### Run in parallel:
```bash
pytest -n 4
```

## Test Cases

{self._format_test_cases_list(test_cases)}

## Configuration

Test configuration is managed in `conftest.py`. Key settings:
- Target URL: {target_config.get('url', 'Not specified')}
- Browser: {target_config.get('browser', 'chromium')}
- Headless: True
- Timeout: 30s

## Generated by
RAG Test Case Generator - Automated Script Generation
"""

    def _format_test_cases_list(self, test_cases: List[Dict]) -> str:
        """Format test cases list for README"""
        lines = []
        for tc in test_cases:
            lines.append(f"- **{tc['id']}**: {tc['title']} ({tc['priority']} priority)")
        return "\n".join(lines)
