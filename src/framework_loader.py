"""
Framework Loader - Parse and extract patterns from test automation framework files
"""

import os
import re
import ast
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class FrameworkLoader:
    """Load and parse test automation framework files"""

    def __init__(self, framework_dir: str = "PSTAF_FRAMEWORK/aut-pstaf/PSTAF_Framework"):
        self.framework_dir = Path(framework_dir)

        # Storage for parsed framework data
        self.framework_files = {}
        self.class_methods = {}
        self.imports = []
        self.global_objects = []
        self.example_test_suite = None

    def load_framework_files(self) -> Dict:
        """Load all framework files and extract patterns"""
        logger.info(f"Loading framework files from: {self.framework_dir}")

        framework_data = {
            'files': {},
            'classes': {},
            'imports': [],
            'global_patterns': [],
            'example': None
        }

        if not self.framework_dir.exists():
            logger.error(f"Framework directory not found: {self.framework_dir}")
            return framework_data

        # Key framework files to load
        key_files = [
            'Initialize.py',
            'ConfigUtils.py',
            'BrowserActions.py',
            'Utils.py',
            'AppAccess.py',
            'Log.py',
            'PSRSClient.py'
        ]

        # Load key framework files
        for file_name in key_files:
            file_path = self.framework_dir / file_name
            if file_path.exists():
                logger.info(f"Parsing framework file: {file_name}")
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    framework_data['files'][file_name] = content

                    # Parse the file
                    parsed_data = self._parse_python_file(content, file_name)
                    framework_data['classes'].update(parsed_data['classes'])
                    framework_data['imports'].extend(parsed_data['imports'])
                    framework_data['global_patterns'].extend(parsed_data['global_patterns'])

                except Exception as e:
                    logger.error(f"Error parsing {file_name}: {str(e)}")
            else:
                logger.warning(f"Framework file not found: {file_name}")

        # Load REST client from subdirectory
        rest_file = self.framework_dir / "REST" / "REST.py"
        if rest_file.exists():
            try:
                with open(rest_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                framework_data['files']['REST.py'] = content
                parsed_data = self._parse_python_file(content, 'REST.py')
                framework_data['classes'].update(parsed_data['classes'])
            except Exception as e:
                logger.error(f"Error parsing REST.py: {str(e)}")

        # Load example test suite (DemoTestSuite.py)
        example_file = self.framework_dir / "DemoTestSuite.py"
        if example_file.exists():
            try:
                with open(example_file, 'r', encoding='utf-8') as f:
                    framework_data['example'] = f.read()
                logger.info("Loaded example test suite (DemoTestSuite.py)")
            except Exception as e:
                logger.error(f"Error loading example test suite: {str(e)}")
        else:
            logger.warning("DemoTestSuite.py not found in framework directory")

        # Remove duplicate imports
        framework_data['imports'] = list(set(framework_data['imports']))

        logger.info(f"Loaded {len(framework_data['files'])} framework files, "
                   f"{len(framework_data['classes'])} classes")

        return framework_data

    def _parse_python_file(self, content: str, file_name: str) -> Dict:
        """Parse Python file and extract classes, methods, imports"""
        parsed_data = {
            'classes': {},
            'imports': [],
            'global_patterns': []
        }

        try:
            tree = ast.parse(content)

            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        import_stmt = f"import {alias.name}"
                        if alias.asname:
                            import_stmt += f" as {alias.asname}"
                        parsed_data['imports'].append(import_stmt)

                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        import_stmt = f"from {module} import {alias.name}"
                        if alias.asname:
                            import_stmt += f" as {alias.asname}"
                        parsed_data['imports'].append(import_stmt)

                # Extract classes and methods
                elif isinstance(node, ast.ClassDef):
                    class_info = self._extract_class_info(node)
                    class_key = f"{file_name.replace('.py', '')}.{node.name}"
                    parsed_data['classes'][class_key] = class_info

            # Extract global variable patterns (e.g., restObj = RestClient())
            global_patterns = self._extract_global_patterns(content)
            parsed_data['global_patterns'].extend(global_patterns)

        except SyntaxError as e:
            logger.error(f"Syntax error parsing {file_name}: {str(e)}")
        except Exception as e:
            logger.error(f"Error parsing {file_name}: {str(e)}")

        return parsed_data

    def _extract_class_info(self, class_node: ast.ClassDef) -> Dict:
        """Extract class information including methods and docstrings"""
        class_info = {
            'name': class_node.name,
            'docstring': ast.get_docstring(class_node),
            'methods': []
        }

        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                method_info = {
                    'name': node.name,
                    'args': [arg.arg for arg in node.args.args],
                    'docstring': ast.get_docstring(node),
                    'returns': self._get_return_annotation(node)
                }
                class_info['methods'].append(method_info)

        return class_info

    def _get_return_annotation(self, func_node: ast.FunctionDef) -> Optional[str]:
        """Extract return type annotation if present"""
        if func_node.returns:
            return ast.unparse(func_node.returns)
        return None

    def _extract_global_patterns(self, content: str) -> List[str]:
        """Extract global object initialization patterns"""
        patterns = []

        # Pattern: variable = ClassName()
        pattern = r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([a-zA-Z_][a-zA-Z0-9_]*)\(\)'

        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                match = re.match(pattern, line)
                if match:
                    patterns.append(line)

        return patterns


    def get_framework_context(self) -> str:
        """Generate framework context for GPT prompt"""
        framework_data = self.load_framework_files()

        context_parts = []

        # Add example test suite first (most important)
        if framework_data['example']:
            context_parts.append("=== EXAMPLE TEST SUITE (FOLLOW THIS PATTERN) ===")
            context_parts.append(framework_data['example'])
            context_parts.append("\n")

        # Add imports
        if framework_data['imports']:
            context_parts.append("=== STANDARD IMPORTS ===")
            context_parts.extend(framework_data['imports'])
            context_parts.append("\n")

        # Add global patterns
        if framework_data['global_patterns']:
            context_parts.append("=== GLOBAL OBJECT INITIALIZATION ===")
            context_parts.extend(framework_data['global_patterns'])
            context_parts.append("\n")

        # Add class information
        if framework_data['classes']:
            context_parts.append("=== AVAILABLE FRAMEWORK CLASSES AND METHODS ===")
            for class_key, class_info in framework_data['classes'].items():
                context_parts.append(f"\nClass: {class_key}")
                if class_info['docstring']:
                    context_parts.append(f"  Description: {class_info['docstring']}")
                context_parts.append("  Methods:")
                for method in class_info['methods']:
                    args_str = ', '.join(method['args'])
                    context_parts.append(f"    - {method['name']}({args_str})")
                    if method['docstring']:
                        context_parts.append(f"      {method['docstring']}")

        return "\n".join(context_parts)

    def get_specific_example(self, example_method_name: str) -> Optional[str]:
        """
        Extract a specific test method from DemoTestSuite

        Args:
            example_method_name: Name of the test method (e.g., 'GEN_002_FUNC_BROWSER_ADMIN_LOGIN')

        Returns:
            Code of the specific method, or None if not found
        """
        if not self.example_test_suite:
            logger.warning("DemoTestSuite not loaded")
            return None

        try:
            import ast
            import inspect

            # Parse the DemoTestSuite code
            tree = ast.parse(self.example_test_suite)

            # Find the class
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Look for the specific method
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef) and item.name == example_method_name:
                            # Extract the method code
                            method_lines = self.example_test_suite.split('\n')
                            start_line = item.lineno - 1
                            end_line = item.end_lineno if hasattr(item, 'end_lineno') else start_line + 50

                            method_code = '\n'.join(method_lines[start_line:end_line])
                            return method_code

            logger.warning(f"Method {example_method_name} not found in DemoTestSuite")
            return None

        except Exception as e:
            logger.error(f"Error extracting example method {example_method_name}: {e}")
            return None

    def get_specific_method(self, class_name: str, method_name: str) -> Optional[str]:
        """
        Get code for a specific method from a framework class

        Args:
            class_name: Name of the class (e.g., 'AppAccess')
            method_name: Name of the method (e.g., 'login')

        Returns:
            Method signature and docstring, or None if not found
        """
        # Look in parsed class methods
        for class_key, class_info in self.class_methods.items():
            if class_name in class_key:
                for method in class_info.get('methods', []):
                    if method['name'] == method_name:
                        # Build method signature
                        args_str = ', '.join(method.get('args', []))
                        signature = f"def {method_name}({args_str})"

                        parts = [signature]
                        if method.get('docstring'):
                            parts.append(f'    """{method["docstring"]}"""')

                        if method.get('returns'):
                            parts.append(f"    # Returns: {method['returns']}")

                        return '\n'.join(parts)

        logger.warning(f"Method {class_name}.{method_name} not found")
        return None

    def get_mandatory_structure(self) -> str:
        """
        Get the mandatory structure components (imports, globals, INITIALIZE, SuiteCleanup)

        Returns:
            String containing all mandatory components
        """
        parts = []

        # Imports
        parts.append("=== REQUIRED IMPORTS ===")
        if self.imports:
            parts.extend(self.imports)
        else:
            # Default imports
            parts.extend([
                "from REST.REST import RestClient",
                "from Initialize import *",
                "from AppAccess import *",
                "from BrowserActions import *",
                "from Utils import *",
                "from Log import *",
                "from PSRSClient import *",
                "from ConfigUtils import ConfigUtils",
                "import sys, time, inspect"
            ])

        parts.append("\n=== GLOBAL OBJECT INITIALIZATION ===")
        if self.global_objects:
            parts.extend(self.global_objects)
        else:
            # Default global objects
            parts.extend([
                "restObj = None",
                "token = None",
                "log = Log()",
                "initObj = Initialize()",
                "util = Utils()",
                "appaccess = AppAccess()",
                "browser = BrowserActions()",
                "restObj = RestClient()"
            ])

        parts.append("\n=== CLASS STRUCTURE ===")
        parts.append("class <TestClassName>(object):")
        parts.append("    ROBOT_LIBRARY_SCOPE = 'GLOBAL'")
        parts.append("    def __init__(self):")
        parts.append("        pass")

        parts.append("\n=== INITIALIZE METHOD (MANDATORY) ===")
        parts.append("""def INITIALIZE(self):
    '''MANDATORY FIRST METHOD - Initialize framework'''
    tc_name = inspect.stack()[0][3]
    try:
        initObj.initialize()
        util.TC_HEADER_FOOTER('Start', tc_name)
        logging.info("Inside Initialize........")
        config = ConfigUtils.getInstance()
        logging.info("ConfigUtils - Value of HOSTNAME..............." + str(config.getConfig('HOSTNAME')))
        util.TC_HEADER_FOOTER('End', tc_name)
    except:
        e = sys.exc_info()[1]
        logging.error("Exception in " + tc_name + "(): " + str(e))
        util.TC_HEADER_FOOTER('End', tc_name)
        raise Exception(e)""")

        parts.append("\n=== SuiteCleanup METHOD (MANDATORY) ===")
        parts.append("""def SuiteCleanup(self):
    '''MANDATORY LAST METHOD - Cleanup'''
    tc_name = inspect.stack()[0][3]
    input_dict = {'filename': tc_name}
    return_dict = {'status': 1}
    try:
        log.setloggingconf()
        util.TC_HEADER_FOOTER('Start', tc_name)
        logging.info("Close All Browsers.... ")
        logging.info("Response = " + str(return_dict))
        assert return_dict['status'] == 1, return_dict['value']
    except:
        e = sys.exc_info()[1]
        logging.error("Exception in " + tc_name + "(): " + str(e))
        util.TC_HEADER_FOOTER('End', tc_name)
        raise Exception(e)
    util.TC_HEADER_FOOTER('End', tc_name)""")

        return "\n".join(parts)

    def list_uploaded_files(self) -> List[Dict]:
        """List all framework files from PSTAF_FRAMEWORK directory"""
        files = []

        if not self.framework_dir.exists():
            logger.warning(f"Framework directory not found: {self.framework_dir}")
            return files

        # List key framework files
        key_files = [
            'Initialize.py',
            'ConfigUtils.py',
            'BrowserActions.py',
            'Utils.py',
            'AppAccess.py',
            'Log.py',
            'PSRSClient.py',
            'DemoTestSuite.py'
        ]

        for file_name in key_files:
            file_path = self.framework_dir / file_name
            if file_path.exists():
                files.append({
                    'name': file_name,
                    'size': file_path.stat().st_size,
                    'modified': file_path.stat().st_mtime
                })

        # Check REST directory
        rest_file = self.framework_dir / "REST" / "REST.py"
        if rest_file.exists():
            files.append({
                'name': 'REST/REST.py',
                'size': rest_file.stat().st_size,
                'modified': rest_file.stat().st_mtime
            })

        return files
