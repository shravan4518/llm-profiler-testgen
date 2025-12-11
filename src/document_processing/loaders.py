"""
Enterprise-grade document loaders with metadata extraction
Supports multiple formats: PDF, TXT, DOCX, MD, JSON
Includes multimodal image processing for PDFs
"""
import os
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json
from datetime import datetime
import config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Import image processor for multimodal capabilities
try:
    from src.document_processing.image_processor import ImageProcessor, integrate_image_descriptions
    IMAGE_PROCESSOR_AVAILABLE = True
except ImportError:
    IMAGE_PROCESSOR_AVAILABLE = False
    logger.warning("Image processor not available")

@dataclass
class Document:
    """Represents a loaded document with metadata"""
    doc_id: str
    filename: str
    content: str
    file_path: str
    file_type: str
    file_size: int
    created_at: str
    modified_at: str
    content_hash: str
    metadata: Dict = None
    page_count: int = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return asdict(self)


class DocumentLoader:
    """Base class for document loaders"""

    @staticmethod
    def generate_doc_id(file_path: str, content: str) -> str:
        """
        Generate unique document ID based on path and content hash

        Args:
            file_path: Path to the document
            content: Document content

        Returns:
            Unique document ID
        """
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
        filename = Path(file_path).stem
        return f"{filename}_{content_hash}"

    @staticmethod
    def get_file_metadata(file_path: str) -> Dict:
        """Extract file system metadata"""
        stat = os.stat(file_path)
        return {
            'file_size': stat.st_size,
            'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat()
        }


class TextLoader(DocumentLoader):
    """Loader for plain text files"""

    @staticmethod
    def load(file_path: str) -> Document:
        """
        Load a text file

        Args:
            file_path: Path to text file

        Returns:
            Document object
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            file_meta = DocumentLoader.get_file_metadata(file_path)
            doc_id = DocumentLoader.generate_doc_id(file_path, content)

            return Document(
                doc_id=doc_id,
                filename=Path(file_path).name,
                content=content,
                file_path=file_path,
                file_type='.txt',
                file_size=file_meta['file_size'],
                created_at=file_meta['created_at'],
                modified_at=file_meta['modified_at'],
                content_hash=hashlib.md5(content.encode('utf-8')).hexdigest()
            )
        except Exception as e:
            logger.error(f"Error loading text file {file_path}: {e}")
            raise


class PDFLoader(DocumentLoader):
    """Loader for PDF files with metadata extraction and multimodal image processing"""

    @staticmethod
    def load(file_path: str) -> Document:
        """
        Load a PDF file with metadata and optional image extraction

        Args:
            file_path: Path to PDF file

        Returns:
            Document object with text and image descriptions
        """
        try:
            import pdfplumber

            content = ""
            metadata = {}
            page_count = 0
            page_texts = {}  # Store text by page for image context

            with pdfplumber.open(file_path) as pdf:
                # Extract PDF metadata
                if pdf.metadata:
                    metadata = {
                        'title': pdf.metadata.get('Title', ''),
                        'author': pdf.metadata.get('Author', ''),
                        'subject': pdf.metadata.get('Subject', ''),
                        'creator': pdf.metadata.get('Creator', ''),
                        'producer': pdf.metadata.get('Producer', ''),
                        'creation_date': pdf.metadata.get('CreationDate', '')
                    }

                # Extract text from all pages
                page_count = len(pdf.pages)
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        # Store page text for image context
                        page_texts[page_num] = page_text

                        # Add page separator for better chunking
                        content += f"\n\n--- Page {page_num} ---\n\n"
                        content += page_text

            logger.info(f"Loaded PDF text: {file_path} ({page_count} pages, {len(content)} chars)")

            # Process images if enabled (MULTIMODAL FEATURE)
            image_descriptions = {}
            if config.ENABLE_IMAGE_PROCESSING and IMAGE_PROCESSOR_AVAILABLE:
                try:
                    logger.info("Processing images from PDF...")
                    image_processor = ImageProcessor()

                    if image_processor.is_available():
                        image_descriptions = image_processor.process_pdf_images(
                            file_path, page_texts
                        )

                        if image_descriptions:
                            # Integrate image descriptions into content
                            content = integrate_image_descriptions(
                                content, page_texts, image_descriptions
                            )
                            logger.info(f"Enhanced content with {sum(len(d) for d in image_descriptions.values())} image descriptions")
                            metadata['has_images'] = True
                            metadata['image_count'] = sum(len(d) for d in image_descriptions.values())
                    else:
                        logger.info("Image processor not available, skipping image processing")

                except Exception as e:
                    logger.warning(f"Image processing failed, continuing with text only: {e}")

            file_meta = DocumentLoader.get_file_metadata(file_path)
            doc_id = DocumentLoader.generate_doc_id(file_path, content)

            logger.info(f"PDF loading complete: {len(content)} total chars (text + images)")

            return Document(
                doc_id=doc_id,
                filename=Path(file_path).name,
                content=content,
                file_path=file_path,
                file_type='.pdf',
                file_size=file_meta['file_size'],
                created_at=file_meta['created_at'],
                modified_at=file_meta['modified_at'],
                content_hash=hashlib.md5(content.encode('utf-8')).hexdigest(),
                metadata=metadata,
                page_count=page_count
            )

        except ImportError:
            logger.error("pdfplumber not installed. Run: pip install pdfplumber")
            raise
        except Exception as e:
            logger.error(f"Error loading PDF {file_path}: {e}")
            raise


class MarkdownLoader(DocumentLoader):
    """Loader for Markdown files"""

    @staticmethod
    def load(file_path: str) -> Document:
        """Load a Markdown file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract title from first H1 if present
            metadata = {}
            lines = content.split('\n')
            if lines and lines[0].startswith('# '):
                metadata['title'] = lines[0].replace('# ', '').strip()

            file_meta = DocumentLoader.get_file_metadata(file_path)
            doc_id = DocumentLoader.generate_doc_id(file_path, content)

            return Document(
                doc_id=doc_id,
                filename=Path(file_path).name,
                content=content,
                file_path=file_path,
                file_type='.md',
                file_size=file_meta['file_size'],
                created_at=file_meta['created_at'],
                modified_at=file_meta['modified_at'],
                content_hash=hashlib.md5(content.encode('utf-8')).hexdigest(),
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Error loading Markdown file {file_path}: {e}")
            raise


class JSONLoader(DocumentLoader):
    """Loader for JSON files"""

    @staticmethod
    def load(file_path: str) -> Document:
        """Load a JSON file and convert to text"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Convert JSON to readable text format
            content = json.dumps(data, indent=2)

            file_meta = DocumentLoader.get_file_metadata(file_path)
            doc_id = DocumentLoader.generate_doc_id(file_path, content)

            return Document(
                doc_id=doc_id,
                filename=Path(file_path).name,
                content=content,
                file_path=file_path,
                file_type='.json',
                file_size=file_meta['file_size'],
                created_at=file_meta['created_at'],
                modified_at=file_meta['modified_at'],
                content_hash=hashlib.md5(content.encode('utf-8')).hexdigest(),
                metadata={'is_json': True}
            )
        except Exception as e:
            logger.error(f"Error loading JSON file {file_path}: {e}")
            raise


class DocumentLoaderFactory:
    """Factory to get appropriate loader based on file type"""

    LOADERS = {
        '.txt': TextLoader,
        '.pdf': PDFLoader,
        '.md': MarkdownLoader,
        '.json': JSONLoader,
        '.py': None  # Will be lazy-loaded from code_loader module
    }

    @classmethod
    def get_loader(cls, file_path: str) -> Optional[DocumentLoader]:
        """
        Get appropriate loader for file type

        Args:
            file_path: Path to document

        Returns:
            Loader class or None if unsupported
        """
        file_ext = Path(file_path).suffix.lower()
        loader = cls.LOADERS.get(file_ext)

        # Lazy load PythonCodeLoader for .py files
        if file_ext == '.py' and loader is None:
            try:
                from src.document_processing.code_loader import PythonCodeLoader
                cls.LOADERS['.py'] = PythonCodeLoader
                loader = PythonCodeLoader
            except ImportError:
                logger.warning("PythonCodeLoader not available, .py files will not be loaded")
                return None

        if loader is None:
            logger.warning(f"Unsupported file type: {file_ext}")

        return loader

    @classmethod
    def load_document(cls, file_path: str) -> Optional[Document]:
        """
        Load document using appropriate loader

        Args:
            file_path: Path to document

        Returns:
            Document object or None if failed
        """
        loader = cls.get_loader(file_path)
        if loader is None:
            return None

        try:
            return loader.load(file_path)
        except Exception as e:
            logger.error(f"Failed to load document {file_path}: {e}")
            return None

    @classmethod
    def load_directory(cls, directory: str) -> List[Document]:
        """
        Load all supported documents from a directory

        Args:
            directory: Path to directory

        Returns:
            List of Document objects
        """
        documents = []
        dir_path = Path(directory)

        if not dir_path.exists():
            logger.error(f"Directory does not exist: {directory}")
            return documents

        for file_path in dir_path.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in cls.LOADERS:
                doc = cls.load_document(str(file_path))
                if doc:
                    documents.append(doc)

        logger.info(f"Loaded {len(documents)} documents from {directory}")
        return documents
