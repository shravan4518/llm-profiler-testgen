"""
Code Loader for ingesting Python framework code into vector database
Adds code-specific metadata and structure preservation
"""
import os
import ast
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import sys

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logger
from src.document_processing.loaders import Document, DocumentLoader

logger = setup_logger(__name__)


class PythonCodeLoader(DocumentLoader):
    """
    Loader for Python source files with code structure analysis
    Extracts functions, classes, and docstrings for better searchability
    """

    @staticmethod
    def extract_code_structure(code: str, file_path: str) -> Dict:
        """
        Extract code structure: classes, functions, imports

        Returns metadata about code organization for better RAG retrieval
        """
        try:
            tree = ast.parse(code)

            structure = {
                'imports': [],
                'classes': [],
                'functions': [],
                'global_variables': []
            }

            for node in ast.walk(tree):
                # Extract imports
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        structure['imports'].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        structure['imports'].append(f"{module}.{alias.name}")

                # Extract classes
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        'name': node.name,
                        'methods': [m.name for m in node.body if isinstance(m, ast.FunctionDef)],
                        'docstring': ast.get_docstring(node) or ''
                    }
                    structure['classes'].append(class_info)

                # Extract top-level functions
                elif isinstance(node, ast.FunctionDef):
                    # Check if it's a top-level function (not a method)
                    if isinstance(getattr(node, 'parent', None), ast.Module) or not hasattr(node, 'parent'):
                        func_info = {
                            'name': node.name,
                            'args': [arg.arg for arg in node.args.args],
                            'docstring': ast.get_docstring(node) or ''
                        }
                        structure['functions'].append(func_info)

            return structure

        except Exception as e:
            logger.warning(f"Could not parse code structure for {file_path}: {e}")
            return {'imports': [], 'classes': [], 'functions': [], 'global_variables': []}

    @staticmethod
    def enhance_code_for_rag(code: str, file_path: str, structure: Dict) -> str:
        """
        Enhance code content with metadata for better RAG retrieval

        Adds structured comments that help LLM understand the code's purpose
        """
        file_name = Path(file_path).name

        # Build enhancement header
        enhancement = f"""
# ============================================================================
# FILE: {file_name}
# PATH: {file_path}
# ============================================================================

# FRAMEWORK COMPONENT SUMMARY:
# This file is part of the Pulse Secure test automation framework.
#
# IMPORTS: {', '.join(structure['imports'][:10])}
#
# CLASSES DEFINED: {', '.join([c['name'] for c in structure['classes']])}
#
# FUNCTIONS DEFINED: {', '.join([f['name'] for f in structure['functions'][:20]])}
#
# ============================================================================

"""
        # Add original code
        enhanced_content = enhancement + code

        return enhanced_content

    @staticmethod
    def load(file_path: str) -> Document:
        """
        Load a Python source file with code structure analysis

        Args:
            file_path: Path to .py file

        Returns:
            Document object with enhanced code content and metadata
        """
        try:
            logger.info(f"Loading Python file: {file_path}")

            # Read source code
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()

            # Extract code structure
            structure = PythonCodeLoader.extract_code_structure(code, file_path)

            # Enhance code with metadata for better RAG
            enhanced_content = PythonCodeLoader.enhance_code_for_rag(code, file_path, structure)

            # Get file metadata
            file_meta = DocumentLoader.get_file_metadata(file_path)
            doc_id = DocumentLoader.generate_doc_id(file_path, code)

            # Build metadata
            metadata = {
                'file_type': 'python_code',
                'language': 'python',
                'classes': [c['name'] for c in structure['classes']],
                'functions': [f['name'] for f in structure['functions']],
                'imports': structure['imports'],
                'is_framework_code': True,
                'purpose': 'test_automation_framework'
            }

            logger.info(f"Loaded Python file: {Path(file_path).name} "
                       f"({len(structure['classes'])} classes, "
                       f"{len(structure['functions'])} functions)")

            return Document(
                doc_id=doc_id,
                filename=Path(file_path).name,
                content=enhanced_content,
                file_path=file_path,
                file_type='.py',
                file_size=file_meta['file_size'],
                created_at=file_meta['created_at'],
                modified_at=file_meta['modified_at'],
                content_hash=hashlib.md5(code.encode('utf-8')).hexdigest(),
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Error loading Python file {file_path}: {e}")
            raise


def load_framework_repository(framework_path: str, include_patterns: List[str] = None) -> List[Document]:
    """
    Load entire framework repository into documents

    Args:
        framework_path: Path to framework root directory
        include_patterns: List of glob patterns to include (default: ['**/*.py'])

    Returns:
        List of Document objects
    """
    if include_patterns is None:
        include_patterns = ['**/*.py']

    framework_path = Path(framework_path)
    documents = []

    logger.info(f"Loading framework from: {framework_path}")

    for pattern in include_patterns:
        for py_file in framework_path.glob(pattern):
            # Skip __pycache__, .pyc files, and test files
            if '__pycache__' in str(py_file) or py_file.suffix == '.pyc':
                continue

            try:
                doc = PythonCodeLoader.load(str(py_file))
                documents.append(doc)
                logger.info(f"✓ Loaded: {py_file.name}")
            except Exception as e:
                logger.warning(f"✗ Failed to load {py_file.name}: {e}")

    logger.info(f"Loaded {len(documents)} Python files from framework")
    return documents
