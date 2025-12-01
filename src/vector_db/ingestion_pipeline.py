"""
Enterprise Ingestion Pipeline
Orchestrates document loading, chunking, and vector store updates
"""
from typing import List, Optional
from pathlib import Path
import config
from src.utils.logger import setup_logger
from src.utils.text_splitter import SemanticTextSplitter
from src.document_processing.loaders import DocumentLoaderFactory, Document
from src.vector_db.vector_store import VectorStore

logger = setup_logger(__name__)


class IngestionPipeline:
    """
    Manages the complete document ingestion workflow:
    1. Load documents
    2. Chunk text
    3. Store in vector database
    """

    def __init__(self, vector_store: VectorStore = None):
        """
        Initialize ingestion pipeline

        Args:
            vector_store: VectorStore instance (creates new if None)
        """
        self.vector_store = vector_store or VectorStore()
        self.text_splitter = SemanticTextSplitter()

    def ingest_file(self, file_path: str) -> bool:
        """
        Ingest a single file

        Args:
            file_path: Path to file

        Returns:
            True if successful
        """
        logger.info(f"Ingesting file: {file_path}")

        # Load document
        document = DocumentLoaderFactory.load_document(file_path)
        if document is None:
            logger.error(f"Failed to load document: {file_path}")
            return False

        # Check if already ingested
        if self.vector_store.document_exists(document.doc_id):
            if not self.vector_store.is_document_updated(document.doc_id, document.content_hash):
                logger.info(f"Document already up-to-date: {document.filename}")
                return True

        # Chunk the document
        logger.info(f"Chunking document: {document.filename}")
        chunks = self.text_splitter.split_text(
            text=document.content,
            doc_id=document.doc_id,
            doc_name=document.filename,
            metadata=document.metadata
        )

        if not chunks:
            logger.warning(f"No chunks generated for: {document.filename}")
            return False

        # Add to vector store
        num_added = self.vector_store.add_chunks(chunks, document)

        if num_added > 0:
            logger.info(f"Successfully ingested '{document.filename}': {num_added} chunks")
            return True
        else:
            logger.error(f"Failed to add chunks for: {document.filename}")
            return False

    def ingest_directory(self, directory: str = None, recursive: bool = True) -> dict:
        """
        Ingest all supported files from a directory

        Args:
            directory: Directory path (uses config.DOCS_DIR if None)
            recursive: Whether to search subdirectories

        Returns:
            Dictionary with ingestion statistics
        """
        if directory is None:
            directory = str(config.DOCS_DIR)

        logger.info(f"Ingesting directory: {directory} (recursive={recursive})")

        # Load all documents
        documents = DocumentLoaderFactory.load_directory(directory)

        if not documents:
            logger.warning(f"No documents found in {directory}")
            return {
                'success': 0,
                'failed': 0,
                'skipped': 0,
                'total': 0
            }

        # Process each document
        stats = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'total': len(documents)
        }

        for document in documents:
            try:
                # Check if already up-to-date
                if self.vector_store.document_exists(document.doc_id):
                    if not self.vector_store.is_document_updated(document.doc_id, document.content_hash):
                        logger.info(f"Skipping up-to-date document: {document.filename}")
                        stats['skipped'] += 1
                        continue

                # Chunk the document
                chunks = self.text_splitter.split_text(
                    text=document.content,
                    doc_id=document.doc_id,
                    doc_name=document.filename,
                    metadata=document.metadata
                )

                if not chunks:
                    logger.warning(f"No chunks for: {document.filename}")
                    stats['failed'] += 1
                    continue

                # Add to vector store
                num_added = self.vector_store.add_chunks(chunks, document)

                if num_added > 0:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1

            except Exception as e:
                logger.error(f"Error processing {document.filename}: {e}")
                stats['failed'] += 1

        logger.info(f"Ingestion complete. Success: {stats['success']}, "
                   f"Failed: {stats['failed']}, Skipped: {stats['skipped']}")

        return stats

    def remove_document(self, doc_id: str) -> bool:
        """
        Remove a document from the vector store

        Args:
            doc_id: Document identifier

        Returns:
            True if successful
        """
        return self.vector_store.remove_document(doc_id)

    def get_stats(self) -> dict:
        """Get vector store statistics"""
        return self.vector_store.get_stats()

    def clear_all(self):
        """Clear all data from vector store"""
        self.vector_store.clear_all()
