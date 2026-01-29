"""
Framework Expert - LLM-based intelligent framework analyzer and context optimizer

This module implements a two-phase LLM expert system:
1. Learning Phase: Analyzes framework once and creates a knowledge base
2. Query Phase: Uses knowledge to identify only relevant code for each test generation
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from openai import AzureOpenAI
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class FrameworkExpert:
    """
    LLM-powered expert that understands framework structure and relationships
    """

    def __init__(self, azure_client: AzureOpenAI, framework_loader,
                 framework_type: str = "pstaff",
                 knowledge_file: str = None):
        """
        Initialize the Framework Expert

        Args:
            azure_client: Azure OpenAI client
            framework_loader: FrameworkLoader instance
            framework_type: "pstaff" or "client" - determines which knowledge file to use
            knowledge_file: Optional custom path. If None, uses framework-specific default
        """
        self.client = azure_client
        self.framework_loader = framework_loader
        self.framework_type = framework_type

        # Use framework-specific knowledge file if not provided
        if knowledge_file is None:
            knowledge_file = f"framework_resources/framework_knowledge_{framework_type}.json"

        self.knowledge_file = Path(knowledge_file)
        self.knowledge_base = None

        # Ensure framework_resources directory exists
        self.knowledge_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"FrameworkExpert initialized for {framework_type} framework")
        logger.info(f"Knowledge file: {self.knowledge_file}")

    def analyze_framework(self, force_reanalysis: bool = False) -> Dict:
        """
        PHASE 1: Analyze framework and create knowledge base

        This is a one-time operation (or when framework changes).
        LLM reads all framework files and creates a structured knowledge base.

        Args:
            force_reanalysis: If True, reanalyze even if knowledge base exists

        Returns:
            Dictionary containing framework knowledge
        """
        # Check if knowledge base already exists
        if not force_reanalysis and self.knowledge_file.exists():
            logger.info(f"Loading existing framework knowledge from {self.knowledge_file}")
            with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                self.knowledge_base = json.load(f)
            return self.knowledge_base

        logger.info("Starting framework analysis with LLM...")

        # Load all framework files
        framework_data = self.framework_loader.load_framework_files()

        # Build comprehensive analysis prompt
        analysis_prompt = self._build_analysis_prompt(framework_data)

        try:
            logger.info(f"Sending framework data to LLM for analysis...")
            logger.info(f"Prompt size: ~{len(analysis_prompt)} characters")

            # Let LLM analyze the framework
            # Note: GPT-5.1 is an o1-series model that uses reasoning tokens internally
            # Need high max_completion_tokens to allow for both reasoning AND output
            response = self.client.chat.completions.create(
                model="gpt-5.1",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert code analyzer specializing in test automation frameworks.
Your task is to analyze a Python test framework and create a comprehensive, searchable knowledge base.
Be thorough and precise - this knowledge will be used to intelligently select relevant code for test generation.
IMPORTANT: Return ONLY valid JSON, no other text."""
                    },
                    {
                        "role": "user",
                        "content": analysis_prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent analysis
                max_completion_tokens=64000  # High limit: o1 models need tokens for reasoning + output
            )

            # Parse LLM response
            logger.info(f"Response object: {response}")
            logger.info(f"Response choices: {len(response.choices) if response.choices else 0}")

            if not response.choices or len(response.choices) == 0:
                logger.error("No choices in response!")
                raise ValueError("LLM returned no choices")

            message = response.choices[0].message
            logger.info(f"Message object: {message}")
            logger.info(f"Message content type: {type(message.content)}")

            analysis_text = message.content
            logger.info(f"Received LLM response: {len(analysis_text) if analysis_text else 0} characters")

            if analysis_text is None:
                logger.error("LLM response content is None!")
                logger.error(f"Finish reason: {response.choices[0].finish_reason}")
                logger.error(f"Full response: {response.model_dump_json()}")
                raise ValueError("LLM response content is None")

            # Extract JSON from response (handle markdown code blocks)
            analysis_text = self._extract_json_from_response(analysis_text)

            if not analysis_text or analysis_text.strip() == "":
                logger.error("Extracted text is empty!")
                logger.error(f"Original response: {response.choices[0].message.content[:500]}")
                raise ValueError("LLM returned empty response after extraction")

            logger.info(f"Attempting to parse JSON ({len(analysis_text)} chars)...")
            self.knowledge_base = self._parse_json_safely(analysis_text)

            # Save to disk
            with open(self.knowledge_file, 'w', encoding='utf-8') as f:
                json.dump(self.knowledge_base, f, indent=2, ensure_ascii=False)

            logger.info(f"Framework analysis complete. Knowledge base saved to {self.knowledge_file}")
            logger.info(f"Analyzed {len(self.knowledge_base.get('classes', {}))} classes")
            logger.info(f"Identified {len(self.knowledge_base.get('test_patterns', {}))} test patterns")

            return self.knowledge_base

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.error(f"Failed to parse: {analysis_text[:500] if 'analysis_text' in locals() else 'N/A'}")
            raise ValueError(f"LLM did not return valid JSON: {e}")
        except Exception as e:
            logger.error(f"Error during framework analysis: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise

    def _extract_json_from_response(self, text: str) -> str:
        """Extract JSON from LLM response, handling various formats"""
        import re

        if not text:
            return ""

        # Try to find JSON in markdown code blocks
        if '```json' in text:
            match = re.search(r'```json\s*([\s\S]*?)\s*```', text)
            if match:
                logger.info("Extracted JSON from ```json block")
                return match.group(1).strip()

        if '```' in text:
            match = re.search(r'```\s*([\s\S]*?)\s*```', text)
            if match:
                extracted = match.group(1).strip()
                if extracted.startswith('{'):
                    logger.info("Extracted JSON from ``` block")
                    return extracted

        # Try to find JSON object directly (starts with { and ends with })
        # Find the first { and last }
        first_brace = text.find('{')
        last_brace = text.rfind('}')

        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_text = text[first_brace:last_brace + 1]
            logger.info(f"Extracted JSON by finding braces (chars {first_brace} to {last_brace})")
            return json_text

        return text.strip()

    def _parse_json_safely(self, text: str) -> Dict:
        """Parse JSON with multiple fallback strategies"""
        import re

        # Strategy 1: Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"Direct JSON parse failed: {e}")

        # Strategy 2: Fix common issues - trailing commas before closing braces
        try:
            fixed = re.sub(r',(\s*[}\]])', r'\1', text)
            return json.loads(fixed)
        except json.JSONDecodeError as e:
            logger.warning(f"Fixed trailing commas parse failed: {e}")

        # Strategy 3: Fix unescaped quotes in strings
        try:
            # This is a simple fix for common issues
            fixed = text.replace('\\"', '__ESCAPED_QUOTE__')
            # Try to fix unescaped quotes (this is a heuristic)
            fixed = re.sub(r'(?<!\\)"(?=[^,:{\[\]}\s])', '\\"', fixed)
            fixed = fixed.replace('__ESCAPED_QUOTE__', '\\"')
            return json.loads(fixed)
        except json.JSONDecodeError as e:
            logger.warning(f"Fixed quotes parse failed: {e}")

        # Strategy 4: Try to truncate at the last valid point
        try:
            # Find matching braces
            depth = 0
            last_valid = -1
            in_string = False
            escape_next = False

            for i, char in enumerate(text):
                if escape_next:
                    escape_next = False
                    continue

                if char == '\\':
                    escape_next = True
                    continue

                if char == '"' and not escape_next:
                    in_string = not in_string
                    continue

                if in_string:
                    continue

                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        last_valid = i
                        break

            if last_valid > 0:
                truncated = text[:last_valid + 1]
                logger.info(f"Trying truncated JSON at position {last_valid}")
                return json.loads(truncated)
        except json.JSONDecodeError as e:
            logger.warning(f"Truncated parse failed: {e}")

        # Strategy 5: Return a minimal valid structure if all else fails
        logger.error("All JSON parsing strategies failed, returning minimal structure")
        logger.error(f"First 1000 chars of failed text: {text[:1000]}")
        logger.error(f"Last 500 chars of failed text: {text[-500:]}")

        return {
            "classes": {},
            "test_patterns": {},
            "mandatory_components": {},
            "common_dependencies": {},
            "_parse_error": "Failed to parse LLM response, using minimal structure"
        }

    def get_relevant_context(self, test_description: str) -> str:
        """
        PHASE 2: Query the expert for relevant code pieces

        Uses the knowledge base to intelligently identify what code is needed
        for the given test description.

        Args:
            test_description: User's test description

        Returns:
            Optimized context string with only relevant code
        """
        # Ensure knowledge base is loaded
        if not self.knowledge_base:
            if self.knowledge_file.exists():
                logger.info("Loading framework knowledge base...")
                try:
                    with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                        self.knowledge_base = json.load(f)
                    logger.info("Knowledge base loaded successfully")
                except Exception as e:
                    logger.error(f"Failed to load knowledge base: {e}")
                    logger.info("Will attempt to reanalyze framework...")
                    self.knowledge_base = None

            if not self.knowledge_base:
                logger.info("No knowledge base found. Analyzing framework...")
                try:
                    self.analyze_framework()
                except Exception as e:
                    logger.error(f"Framework analysis failed: {e}")
                    logger.warning("Falling back to basic context (no LLM optimization)")
                    # Return basic framework context without optimization
                    return self.framework_loader.get_framework_context()

        logger.info(f"Querying expert for: {test_description}")

        # Query LLM expert
        try:
            requirements = self._query_expert(test_description)
        except Exception as e:
            logger.error(f"Expert query failed: {e}")
            logger.warning("Falling back to basic context")
            return self.framework_loader.get_framework_context()

        # Build optimized context from requirements
        try:
            optimized_context = self._build_optimized_context(requirements)
        except Exception as e:
            logger.error(f"Context building failed: {e}")
            logger.warning("Falling back to basic context")
            return self.framework_loader.get_framework_context()

        logger.info(f"Context optimized: ~{len(optimized_context)} characters")
        logger.info(f"Estimated tokens: ~{len(optimized_context) // 4}")

        return optimized_context

    def _build_analysis_prompt(self, framework_data: Dict) -> str:
        """Build comprehensive prompt for framework analysis"""

        if self.framework_type == "client":
            return self._build_client_analysis_prompt(framework_data)
        else:
            return self._build_pstaff_analysis_prompt(framework_data)

    def _build_pstaff_analysis_prompt(self, framework_data: Dict) -> str:
        """Build analysis prompt for PSTAFF (Robot Framework) """

        prompt = f"""Analyze this Python test automation framework (PSTAF) and create a comprehensive knowledge base.

=== FRAMEWORK FILES ===

{self._format_framework_data(framework_data)}

=== YOUR TASK ===

Create a JSON knowledge base that captures:

1. **Classes**: For each framework class, document:
   - Purpose and functionality
   - Key methods with signatures
   - Dependencies on other classes
   - Return value patterns

2. **Test Patterns**: From DemoTestSuite, identify:
   - Common test patterns (admin login, user login, REST API calls, etc.)
   - The example test method name
   - Required classes and methods
   - Flow/sequence of operations
   - What each pattern is used for

3. **Method Relationships**: For key methods, document:
   - What methods they call
   - What they depend on
   - Input/output formats
   - Common usage patterns

4. **Mandatory Components**: Identify:
   - Required imports for different test types
   - Global object initialization pattern
   - INITIALIZE method structure
   - SuiteCleanup method structure

=== OUTPUT FORMAT ===

Return a JSON structure like this:

{{
  "classes": {{
    "AppAccess": {{
      "purpose": "Browser-based authentication and access control",
      "key_methods": {{
        "login": {{
          "signature": "login(self, login_dict)",
          "purpose": "Perform browser login",
          "requires": ["BrowserActions", "ConfigUtils"],
          "input_format": "dict with type, url, username, password",
          "output_format": "dict with status (1/0) and value",
          "used_in_patterns": ["browser_admin_login", "browser_user_login"]
        }},
        "logout": {{...}}
      }},
      "depends_on": ["BrowserActions", "ConfigUtils"]
    }},
    "BrowserActions": {{...}},
    "Utils": {{...}},
    ...
  }},
  "test_patterns": {{
    "browser_admin_login": {{
      "example_method": "GEN_002_FUNC_BROWSER_ADMIN_LOGIN",
      "description": "Browser-based admin authentication test",
      "required_classes": ["AppAccess", "BrowserActions", "Utils", "ConfigUtils"],
      "required_methods": [
        {{"class": "AppAccess", "method": "login"}},
        {{"class": "AppAccess", "method": "logout"}},
        {{"class": "BrowserActions", "method": "close_browser_window"}},
        {{"class": "Utils", "method": "TC_HEADER_FOOTER"}}
      ],
      "flow": "login -> wait -> verify -> logout -> close",
      "keywords": ["admin", "login", "authentication", "browser", "GUI"]
    }},
    "browser_user_login": {{...}},
    "rest_api_call": {{...}},
    ...
  }},
  "mandatory_components": {{
    "imports": [
      "from REST.REST import RestClient",
      "from Initialize import *",
      "from AppAccess import *",
      ...
    ],
    "global_objects": [
      "restObj = None",
      "log = Log()",
      "initObj = Initialize()",
      ...
    ],
    "class_structure": [
      "ROBOT_LIBRARY_SCOPE = 'GLOBAL'",
      "def __init__(self): pass",
      "def INITIALIZE(self): ...",
      "def SuiteCleanup(self): ..."
    ]
  }},
  "common_dependencies": {{
    "browser_tests": ["AppAccess", "BrowserActions", "Utils", "ConfigUtils", "Log"],
    "rest_tests": ["RestClient", "Utils", "ConfigUtils", "Log"],
    "all_tests": ["Initialize", "Utils", "Log"]
  }}
}}

Be comprehensive and precise. This knowledge base will be used to intelligently select relevant code pieces for test generation.
"""
        return prompt

    def _build_client_analysis_prompt(self, framework_data: Dict) -> str:
        """Build analysis prompt for Client (aut-pypdc/pytest) framework"""

        prompt = f"""Analyze this Python test automation framework (aut-pypdc Client Framework) and create a comprehensive knowledge base.

=== FRAMEWORK FILES ===

{self._format_framework_data(framework_data)}

=== YOUR TASK ===

Create a JSON knowledge base that captures:

1. **Classes**: For each framework class, document:
   - Purpose and functionality
   - Key methods with signatures
   - Dependencies on other classes
   - Return value patterns

2. **Test Patterns**: From the examples, identify:
   - Common test patterns (PPS REST API calls, authentication, configuration, etc.)
   - The example test method names (TC_001_..., TC_002_..., etc.)
   - Required classes and methods (PpsRestClient, FWUtils, Initialize, etc.)
   - Flow/sequence of operations
   - What each pattern is used for

3. **Method Relationships**: For key methods, document:
   - What methods they call
   - What they depend on
   - Input/output formats
   - Common usage patterns

4. **Mandatory Components**: Identify:
   - Required imports for different test types
   - Global object initialization pattern
   - INITIALIZE function structure
   - CLEANUP function structure

=== OUTPUT FORMAT ===

Return a JSON structure like this:

{{
  "classes": {{
    "PpsRestClient": {{
      "purpose": "REST API client for PPS/Profiler operations",
      "key_methods": {{
        "execute_request": {{
          "signature": "execute_request(self, resource_uri, method_type, payload=None)",
          "purpose": "Execute REST API request",
          "requires": ["authentication"],
          "input_format": "uri string, method type (GET/PUT/POST/DELETE), optional payload dict",
          "output_format": "Response object with status_code and json()",
          "used_in_patterns": ["rest_api_config", "rest_api_verify"]
        }}
      }},
      "depends_on": ["Authentication"]
    }},
    "FWUtils": {{...}},
    "Initialize": {{...}},
    ...
  }},
  "test_patterns": {{
    "rest_api_config": {{
      "example_method": "TC_001_PPS_CONFIGURE_WMI",
      "description": "Configure PPS settings via REST API",
      "required_classes": ["PpsRestClient", "FWUtils", "Initialize", "CommonUtils"],
      "required_methods": [
        {{"class": "PpsRestClient", "method": "execute_request"}},
        {{"class": "Initialize", "method": "initialize"}},
        {{"class": "CommonUtils", "method": "get_screenshot"}}
      ],
      "flow": "INITIALIZE -> configure via REST -> verify -> CLEANUP",
      "keywords": ["REST", "API", "configuration", "PPS", "profiler"]
    }},
    "authentication_test": {{...}},
    ...
  }},
  "mandatory_components": {{
    "imports": [
      "from FWUtils import FWUtils",
      "from Initialize import Initialize",
      "from CommonUtils import CommonUtils",
      "from admin_pps.PpsRestUtils import PpsRestClient",
      "import sys"
    ],
    "global_objects": [
      "objFwUtils = FWUtils()",
      "log = objFwUtils.get_logger(__name__, 1)",
      "objInitialize = Initialize()",
      "objCommonUtils = CommonUtils()",
      "pps_client = PpsRestClient()"
    ],
    "function_structure": [
      "def INITIALIZE(): ...",
      "def TC_<ID>_PPS_<DESCRIPTION>(): ...",
      "def CLEANUP(): ..."
    ]
  }},
  "common_dependencies": {{
    "rest_tests": ["PpsRestClient", "FWUtils", "Initialize", "CommonUtils"],
    "all_tests": ["FWUtils", "Initialize", "CommonUtils"]
  }}
}}

Be comprehensive and precise. This knowledge base will be used to intelligently select relevant code pieces for test generation.
"""
        return prompt

    def _format_framework_data(self, framework_data: Dict) -> str:
        """Format framework data for LLM analysis"""

        parts = []

        # Add example test suite (most important)
        if framework_data.get('example'):
            parts.append("=== EXAMPLE TEST SUITE (DemoTestSuite.py) ===")
            parts.append(framework_data['example'])
            parts.append("\n")

        # Add Robot Framework examples (for learning patterns)
        if framework_data.get('robot_examples'):
            parts.append("=== ROBOT FRAMEWORK EXAMPLES (For Learning Patterns) ===")
            parts.append("IMPORTANT: These are EXAMPLES to learn patterns from, NOT templates to copy!")
            parts.append("Study the structure, syntax, and conventions - then create unique implementations.\n")

            for example in framework_data['robot_examples']:
                if example.get('robot_content'):
                    parts.append(f"\n--- Example Robot File: {example['robot_file']} ---")
                    parts.append(example['robot_content'])

                if example.get('data_content'):
                    parts.append(f"\n--- Example Data File: {example['data_file']} ---")
                    parts.append(example['data_content'])

            parts.append("\n")

        # Add class information
        if framework_data.get('classes'):
            parts.append("=== FRAMEWORK CLASSES ===")
            for class_key, class_info in framework_data['classes'].items():
                parts.append(f"\nClass: {class_key}")
                if class_info.get('docstring'):
                    parts.append(f"Description: {class_info['docstring']}")
                parts.append("Methods:")
                for method in class_info.get('methods', []):
                    args_str = ', '.join(method.get('args', []))
                    parts.append(f"  - {method['name']}({args_str})")
                    if method.get('docstring'):
                        parts.append(f"    {method['docstring']}")

        # Add imports
        if framework_data.get('imports'):
            parts.append("\n=== STANDARD IMPORTS ===")
            parts.extend(framework_data['imports'])

        # Add global patterns
        if framework_data.get('global_patterns'):
            parts.append("\n=== GLOBAL OBJECT PATTERNS ===")
            parts.extend(framework_data['global_patterns'])

        return "\n".join(parts)

    def _query_expert(self, test_description: str) -> Dict:
        """Query LLM expert to identify required components"""

        query_prompt = f"""You are a framework expert with comprehensive knowledge of the PSTAF test automation framework.

=== FRAMEWORK KNOWLEDGE BASE ===
{json.dumps(self.knowledge_base, indent=2)}

=== USER REQUEST ===
The user wants to create a test: "{test_description}"

=== YOUR TASK ===
Based on your framework knowledge, identify EXACTLY what code pieces are needed.

Analyze:
1. What is the user's intent? (browser test, REST test, login, verification, etc.)
2. Which test pattern from DemoTestSuite is most similar?
3. What specific classes and methods are required?
4. What dependencies are needed?
5. What's the expected flow?

Return JSON in this EXACT format:
{{
  "intent_analysis": "Brief description of what user wants",
  "best_matching_pattern": "pattern_key from knowledge base",
  "similar_example_method": "Exact method name from DemoTestSuite",
  "required_methods": [
    {{"class": "AppAccess", "method": "login", "why": "performs login"}},
    {{"class": "AppAccess", "method": "logout", "why": "performs logout"}},
    {{"class": "BrowserActions", "method": "close_browser_window", "why": "cleanup"}},
    {{"class": "Utils", "method": "TC_HEADER_FOOTER", "why": "test markers"}}
  ],
  "required_classes": ["AppAccess", "BrowserActions", "Utils", "ConfigUtils"],
  "test_type": "browser" or "rest" or "hybrid",
  "expected_flow": "INITIALIZE -> login -> verify -> logout -> close -> SuiteCleanup",
  "special_considerations": ["Any special notes or warnings"]
}}

Be precise - only include what's truly needed. The goal is to minimize context while maintaining completeness.
"""

        try:
            logger.info("Sending query to LLM expert...")
            response = self.client.chat.completions.create(
                model="gpt-5.1",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a framework expert. Analyze requests and identify required code components. Return only valid JSON."
                    },
                    {
                        "role": "user",
                        "content": query_prompt
                    }
                ],
                temperature=0.1,
                max_completion_tokens=1500
            )

            response_text = response.choices[0].message.content
            logger.info(f"Expert response received: {len(response_text)} characters")

            # Extract JSON
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
                logger.info("Extracted from json markdown")
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
                logger.info("Extracted from markdown")

            if not response_text:
                logger.error("Empty response after extraction!")
                raise ValueError("Empty response from LLM")

            requirements = json.loads(response_text)

            logger.info(f"Expert identified pattern: {requirements.get('best_matching_pattern')}")
            logger.info(f"Required methods: {len(requirements.get('required_methods', []))}")

            return requirements

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in expert query: {e}")
            logger.error(f"Failed text: {response_text[:500] if 'response_text' in locals() else 'N/A'}")
            # Fallback to basic requirements
            logger.warning("Using fallback requirements")
            return {
                "intent_analysis": test_description,
                "similar_example_method": "GEN_002_FUNC_BROWSER_ADMIN_LOGIN",
                "required_methods": [],
                "required_classes": ["AppAccess", "BrowserActions", "Utils"],
                "test_type": "browser",
                "expected_flow": "INITIALIZE -> test -> SuiteCleanup"
            }
        except Exception as e:
            logger.error(f"Error querying expert: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fallback to basic requirements
            logger.warning("Using fallback requirements due to exception")
            return {
                "intent_analysis": test_description,
                "similar_example_method": "GEN_002_FUNC_BROWSER_ADMIN_LOGIN",
                "required_methods": [],
                "required_classes": ["AppAccess", "BrowserActions", "Utils"],
                "test_type": "browser",
                "expected_flow": "INITIALIZE -> test -> SuiteCleanup"
            }

    def _build_optimized_context(self, requirements: Dict) -> str:
        """Build minimal context with only required components"""

        context_parts = []

        # 1. Add the most similar example from DemoTestSuite
        similar_example = requirements.get('similar_example_method')
        if similar_example:
            context_parts.append(f"=== MOST SIMILAR EXAMPLE: {similar_example} ===")
            example_code = self.framework_loader.get_specific_example(similar_example)
            if example_code:
                context_parts.append(example_code)
            else:
                # Fallback: include full DemoTestSuite
                logger.warning(f"Could not find specific example {similar_example}, using full suite")
                context_parts.append(self.framework_loader.example_test_suite or "")
            context_parts.append("\n")

        # 2. Add only required methods (not entire classes)
        if requirements.get('required_methods'):
            context_parts.append("=== REQUIRED FRAMEWORK METHODS ===")
            for method_req in requirements['required_methods']:
                class_name = method_req.get('class')
                method_name = method_req.get('method')
                why = method_req.get('why', '')

                method_code = self.framework_loader.get_specific_method(class_name, method_name)
                if method_code:
                    context_parts.append(f"\n{class_name}.{method_name}:")
                    if why:
                        context_parts.append(f"  Purpose: {why}")
                    context_parts.append(method_code)
            context_parts.append("\n")

        # 3. Add mandatory structure (always needed)
        context_parts.append("=== MANDATORY STRUCTURE ===")
        mandatory = self.framework_loader.get_mandatory_structure()
        context_parts.append(mandatory)

        # 4. Add flow guidance
        if requirements.get('expected_flow'):
            context_parts.append(f"\n=== EXPECTED FLOW ===")
            context_parts.append(requirements['expected_flow'])

        return "\n".join(context_parts)

    def get_knowledge_stats(self) -> Dict:
        """Get statistics about the framework knowledge base"""

        if not self.knowledge_base:
            if self.knowledge_file.exists():
                with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                    self.knowledge_base = json.load(f)
            else:
                return {"status": "not_analyzed", "framework_type": self.framework_type}

        return {
            "status": "ready",
            "framework_type": self.framework_type,
            "classes_count": len(self.knowledge_base.get('classes', {})),
            "patterns_count": len(self.knowledge_base.get('test_patterns', {})),
            "knowledge_file": str(self.knowledge_file),
            "file_exists": self.knowledge_file.exists()
        }

    def ingest_files(self, file_contents: List[Dict]) -> Dict:
        """
        Ingest new files into the existing knowledge base

        Args:
            file_contents: List of dicts with 'filename' and 'content' keys

        Returns:
            Dict with ingestion results
        """
        logger.info(f"Ingesting {len(file_contents)} files into {self.framework_type} knowledge base")

        # Load existing knowledge base if it exists
        if self.knowledge_file.exists():
            with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                self.knowledge_base = json.load(f)
        else:
            self.knowledge_base = {
                "classes": {},
                "test_patterns": {},
                "mandatory_components": {},
                "common_dependencies": {}
            }

        # Format the new files for analysis
        files_text = "\n\n".join([
            f"=== FILE: {f['filename']} ===\n{f['content']}"
            for f in file_contents
        ])

        # Build incremental analysis prompt
        increment_prompt = f"""You are analyzing additional files for the {self.framework_type.upper()} test automation framework.

=== EXISTING KNOWLEDGE BASE ===
{json.dumps(self.knowledge_base, indent=2)}

=== NEW FILES TO ANALYZE ===
{files_text}

=== YOUR TASK ===
Analyze the new files and UPDATE the knowledge base:
1. Add any NEW classes found to the "classes" section
2. Add any NEW test patterns found to "test_patterns" section
3. Update "mandatory_components" if new required imports or patterns are found
4. Update "common_dependencies" if new dependency patterns emerge

IMPORTANT:
- MERGE new information with existing knowledge
- Do NOT remove existing entries
- Only ADD or UPDATE based on new files

Return the COMPLETE UPDATED knowledge base as JSON.
"""

        try:
            logger.info("Sending incremental analysis to LLM...")
            response = self.client.chat.completions.create(
                model="gpt-5.1",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert code analyzer. Analyze new framework files and merge them into an existing knowledge base. Return only valid JSON."
                    },
                    {
                        "role": "user",
                        "content": increment_prompt
                    }
                ],
                temperature=0.1,
                max_completion_tokens=64000
            )

            analysis_text = response.choices[0].message.content

            # Extract JSON
            if '```json' in analysis_text:
                analysis_text = analysis_text.split('```json')[1].split('```')[0].strip()
            elif '```' in analysis_text:
                analysis_text = analysis_text.split('```')[1].split('```')[0].strip()

            updated_knowledge = json.loads(analysis_text)

            # Save updated knowledge base
            self.knowledge_base = updated_knowledge
            with open(self.knowledge_file, 'w', encoding='utf-8') as f:
                json.dump(self.knowledge_base, f, indent=2, ensure_ascii=False)

            logger.info(f"Knowledge base updated successfully")
            logger.info(f"Classes: {len(self.knowledge_base.get('classes', {}))}")
            logger.info(f"Patterns: {len(self.knowledge_base.get('test_patterns', {}))}")

            return {
                "success": True,
                "files_ingested": len(file_contents),
                "classes_count": len(self.knowledge_base.get('classes', {})),
                "patterns_count": len(self.knowledge_base.get('test_patterns', {})),
                "knowledge_file": str(self.knowledge_file)
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return {"success": False, "error": f"Failed to parse LLM response: {e}"}
        except Exception as e:
            logger.error(f"Error during file ingestion: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}
