"""
Enterprise Vector Store with Advanced Features
- Metadata tracking
- Document versioning
- Deduplication
- Incremental updates
- Hybrid search support
"""
import os
import pickle
import faiss
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from sentence_transformers import SentenceTransformer
import config
from src.utils.logger import setup_logger
from src.utils.text_splitter import Chunk
from src.document_processing.loaders import Document

logger = setup_logger(__name__)


@dataclass
class ChunkMetadata:
    """Extended metadata for each chunk in the vector store"""
    chunk_id: str
    doc_id: str
    doc_name: str
    chunk_index: int
    text: str
    embedding_vector_id: int  # Index in FAISS
    start_char: int
    end_char: int
    page_number: Optional[int] = None
    section: Optional[str] = None
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


@dataclass
class DocumentRegistry:
    """Registry to track ingested documents"""
    doc_id: str
    filename: str
    file_path: str
    content_hash: str
    chunk_ids: List[str]
    ingested_at: str
    last_updated: str
    num_chunks: int


class VectorStore:
    """
    Enterprise-grade vector store built on FAISS
    Manages embeddings, metadata, and document registry
    """

    def __init__(
        self,
        index_path: str = str(config.FAISS_INDEX_PATH),
        metadata_path: str = str(config.CHUNK_METADATA_PATH),
        registry_path: str = str(config.DOC_REGISTRY_PATH),
        embedding_model: str = config.EMBED_MODEL_NAME,
        dimension: int = config.EMBED_DIM
    ):
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.registry_path = registry_path
        self.dimension = dimension

        # Initialize FAISS index
        self.index = self._load_or_create_index()

        # Load metadata and registry
        self.chunk_metadata: Dict[int, ChunkMetadata] = self._load_metadata()
        self.doc_registry: Dict[str, DocumentRegistry] = self._load_registry()

        # Load embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)

    def _load_or_create_index(self) -> faiss.Index:
        """Load existing FAISS index or create new one"""
        if os.path.exists(self.index_path):
            logger.info(f"Loading existing FAISS index from {self.index_path}")
            index = faiss.read_index(self.index_path)
            logger.info(f"Loaded index with {index.ntotal} vectors")
            return index
        else:
            logger.info(f"Creating new FAISS index (dimension={self.dimension})")
            index = faiss.IndexFlatL2(self.dimension)
            self._save_index(index)
            return index

    def _save_index(self, index: faiss.Index = None):
        """Save FAISS index to disk"""
        if index is None:
            index = self.index
        faiss.write_index(index, self.index_path)
        logger.debug(f"Saved FAISS index to {self.index_path}")

    def _load_metadata(self) -> Dict[int, ChunkMetadata]:
        """Load chunk metadata from disk"""
        if os.path.exists(self.metadata_path):
            with open(self.metadata_path, 'rb') as f:
                metadata = pickle.load(f)
            logger.info(f"Loaded {len(metadata)} chunk metadata entries")
            return metadata
        return {}

    def _save_metadata(self):
        """Save chunk metadata to disk"""
        with open(self.metadata_path, 'wb') as f:
            pickle.dump(self.chunk_metadata, f)
        logger.debug(f"Saved {len(self.chunk_metadata)} metadata entries")

    def _load_registry(self) -> Dict[str, DocumentRegistry]:
        """Load document registry from disk"""
        if os.path.exists(self.registry_path):
            with open(self.registry_path, 'rb') as f:
                registry = pickle.load(f)
            logger.info(f"Loaded registry with {len(registry)} documents")
            return registry
        return {}

    def _save_registry(self):
        """Save document registry to disk"""
        with open(self.registry_path, 'wb') as f:
            pickle.dump(self.doc_registry, f)
        logger.debug(f"Saved registry with {len(self.doc_registry)} documents")

    def document_exists(self, doc_id: str) -> bool:
        """Check if document already exists in the store"""
        return doc_id in self.doc_registry

    def is_document_updated(self, doc_id: str, content_hash: str) -> bool:
        """
        Check if document has been updated since last ingestion

        Args:
            doc_id: Document identifier
            content_hash: Current content hash

        Returns:
            True if document is different from stored version
        """
        if doc_id not in self.doc_registry:
            return True
        return self.doc_registry[doc_id].content_hash != content_hash

    def add_chunks(self, chunks: List[Chunk], document: Document) -> int:
        """
        Add chunks to the vector store

        Args:
            chunks: List of Chunk objects
            document: Source document

        Returns:
            Number of chunks added
        """
        if not chunks:
            logger.warning(f"No chunks to add for document {document.doc_id}")
            return 0

        # Check for duplicates
        if self.document_exists(document.doc_id):
            if not self.is_document_updated(document.doc_id, document.content_hash):
                logger.info(f"Document {document.doc_id} already exists with same content. Skipping.")
                return 0
            else:
                logger.info(f"Document {document.doc_id} has been updated. Removing old version.")
                self.remove_document(document.doc_id)

        # Extract text from chunks
        texts = [chunk.text for chunk in chunks]

        # Generate embeddings
        logger.info(f"Generating embeddings for {len(texts)} chunks...")
        embeddings = self.embedding_model.encode(
            texts,
            batch_size=config.EMBED_BATCH_SIZE,
            show_progress_bar=True
        ).astype('float32')

        # Get current index size
        current_size = self.index.ntotal

        # Add embeddings to FAISS
        self.index.add(embeddings)
        logger.info(f"Added {len(embeddings)} vectors to FAISS index")

        # Store metadata for each chunk
        chunk_ids = []
        for i, chunk in enumerate(chunks):
            vector_id = current_size + i
            chunk_metadata = ChunkMetadata(
                chunk_id=chunk.chunk_id,
                doc_id=chunk.doc_id,
                doc_name=chunk.doc_name,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                embedding_vector_id=vector_id,
                start_char=chunk.start_char,
                end_char=chunk.end_char,
                page_number=chunk.page_number,
                section=chunk.section
            )
            self.chunk_metadata[vector_id] = chunk_metadata
            chunk_ids.append(chunk.chunk_id)

        # Update document registry
        doc_registry = DocumentRegistry(
            doc_id=document.doc_id,
            filename=document.filename,
            file_path=document.file_path,
            content_hash=document.content_hash,
            chunk_ids=chunk_ids,
            ingested_at=datetime.now().isoformat(),
            last_updated=datetime.now().isoformat(),
            num_chunks=len(chunks)
        )
        self.doc_registry[document.doc_id] = doc_registry

        # Persist to disk
        self._save_index()
        self._save_metadata()
        self._save_registry()

        logger.info(f"Successfully added {len(chunks)} chunks from document '{document.filename}'")
        return len(chunks)

    def search(
        self,
        query: str,
        k: int = config.DEFAULT_TOP_K,
        score_threshold: float = None
    ) -> List[Tuple[ChunkMetadata, float]]:
        """
        Search for similar chunks

        Args:
            query: Search query text
            k: Number of results to return
            score_threshold: Minimum similarity score (optional)

        Returns:
            List of (ChunkMetadata, similarity_score) tuples
        """
        if self.index.ntotal == 0:
            logger.warning("Index is empty. Please ingest documents first.")
            return []

        # Generate query embedding
        query_embedding = self.embedding_model.encode([query]).astype('float32')

        # Search in FAISS
        distances, indices = self.index.search(query_embedding, k)

        # Convert L2 distances to similarity scores (inverse)
        # Lower distance = higher similarity
        # Normalize to 0-1 range (approximate)
        max_dist = np.max(distances[0]) if len(distances[0]) > 0 else 1.0
        similarities = 1 - (distances[0] / (max_dist + 1e-6))

        # Collect results with metadata
        results = []
        for idx, similarity in zip(indices[0], similarities):
            if idx == -1:  # FAISS returns -1 for invalid indices
                continue

            # Apply score threshold if provided
            if score_threshold and similarity < score_threshold:
                continue

            if idx in self.chunk_metadata:
                results.append((self.chunk_metadata[idx], float(similarity)))

        logger.info(f"Found {len(results)} results for query: '{query}'")
        return results

    def remove_document(self, doc_id: str) -> bool:
        """
        Remove a document and its chunks from the store

        Note: FAISS doesn't support deletion, so we rebuild the index

        Args:
            doc_id: Document identifier

        Returns:
            True if successful
        """
        if doc_id not in self.doc_registry:
            logger.warning(f"Document {doc_id} not found in registry")
            return False

        # Get chunk IDs to remove
        doc_info = self.doc_registry[doc_id]
        vector_ids_to_remove = [
            meta.embedding_vector_id
            for meta in self.chunk_metadata.values()
            if meta.doc_id == doc_id
        ]

        # Remove from metadata
        for vid in vector_ids_to_remove:
            if vid in self.chunk_metadata:
                del self.chunk_metadata[vid]

        # Remove from registry
        del self.doc_registry[doc_id]

        # Rebuild FAISS index (expensive operation)
        logger.info(f"Rebuilding FAISS index after removing document {doc_id}")
        self._rebuild_index()

        logger.info(f"Removed document {doc_id} and {len(vector_ids_to_remove)} chunks")
        return True

    def _rebuild_index(self):
        """Rebuild FAISS index from remaining chunks"""
        if not self.chunk_metadata:
            # No chunks left, create empty index
            self.index = faiss.IndexFlatL2(self.dimension)
            self._save_index()
            self._save_metadata()
            self._save_registry()
            return

        # Extract all texts
        sorted_metadata = sorted(self.chunk_metadata.items(), key=lambda x: x[0])
        texts = [meta.text for _, meta in sorted_metadata]

        # Regenerate embeddings
        logger.info(f"Regenerating embeddings for {len(texts)} chunks...")
        embeddings = self.embedding_model.encode(
            texts,
            batch_size=config.EMBED_BATCH_SIZE,
            show_progress_bar=True
        ).astype('float32')

        # Create new index
        new_index = faiss.IndexFlatL2(self.dimension)
        new_index.add(embeddings)

        # Update vector IDs in metadata
        new_metadata = {}
        for new_id, (old_id, meta) in enumerate(sorted_metadata):
            meta.embedding_vector_id = new_id
            new_metadata[new_id] = meta

        self.index = new_index
        self.chunk_metadata = new_metadata

        # Save
        self._save_index()
        self._save_metadata()
        self._save_registry()

    def get_stats(self) -> Dict:
        """Get statistics about the vector store"""
        return {
            'total_documents': len(self.doc_registry),
            'total_chunks': len(self.chunk_metadata),
            'total_vectors': self.index.ntotal,
            'embedding_dimension': self.dimension,
            'documents': [
                {
                    'doc_id': reg.doc_id,
                    'filename': reg.filename,
                    'num_chunks': reg.num_chunks,
                    'ingested_at': reg.ingested_at
                }
                for reg in self.doc_registry.values()
            ]
        }

    def clear_all(self):
        """Clear all data from the vector store"""
        logger.warning("Clearing all data from vector store")
        self.index = faiss.IndexFlatL2(self.dimension)
        self.chunk_metadata = {}
        self.doc_registry = {}
        self._save_index()
        self._save_metadata()
        self._save_registry()
        logger.info("Vector store cleared")
