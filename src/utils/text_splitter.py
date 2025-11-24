"""
Advanced text splitting with semantic awareness
Implements multiple chunking strategies for optimal retrieval
"""
import re
from typing import List, Dict
from dataclasses import dataclass
import config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class Chunk:
    """Represents a text chunk with metadata"""
    text: str
    chunk_id: str
    doc_id: str
    doc_name: str
    chunk_index: int
    start_char: int
    end_char: int
    page_number: int = None
    section: str = None

class SemanticTextSplitter:
    """
    Advanced text splitter that respects document structure
    Uses paragraph boundaries, sentence boundaries, and semantic units
    """

    def __init__(
        self,
        chunk_size: int = config.CHUNK_SIZE,
        chunk_overlap: int = config.CHUNK_OVERLAP,
        min_chunk_size: int = config.MIN_CHUNK_SIZE
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def split_text(
        self,
        text: str,
        doc_id: str,
        doc_name: str,
        metadata: Dict = None
    ) -> List[Chunk]:
        """
        Split text into semantically coherent chunks

        Args:
            text: Input text to split
            doc_id: Unique document identifier
            doc_name: Document filename
            metadata: Additional document metadata

        Returns:
            List of Chunk objects
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            logger.warning(f"Text too short to chunk: {len(text)} chars")
            return []

        # Normalize text
        text = self._normalize_text(text)

        # Split by paragraphs first
        paragraphs = self._split_paragraphs(text)

        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_index = 0

        for para in paragraphs:
            # If adding this paragraph exceeds chunk size
            if len(current_chunk) + len(para) > self.chunk_size:
                # Save current chunk if it's substantial
                if len(current_chunk.strip()) >= self.min_chunk_size:
                    chunk_obj = Chunk(
                        text=current_chunk.strip(),
                        chunk_id=f"{doc_id}_chunk_{chunk_index}",
                        doc_id=doc_id,
                        doc_name=doc_name,
                        chunk_index=chunk_index,
                        start_char=current_start,
                        end_char=current_start + len(current_chunk),
                        page_number=metadata.get('page_number') if metadata else None,
                        section=metadata.get('section') if metadata else None
                    )
                    chunks.append(chunk_obj)
                    chunk_index += 1

                    # Start new chunk with overlap
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_start = current_start + len(current_chunk) - len(overlap_text)
                    current_chunk = overlap_text + para
                else:
                    current_chunk += para
            else:
                current_chunk += para

        # Add final chunk
        if len(current_chunk.strip()) >= self.min_chunk_size:
            chunk_obj = Chunk(
                text=current_chunk.strip(),
                chunk_id=f"{doc_id}_chunk_{chunk_index}",
                doc_id=doc_id,
                doc_name=doc_name,
                chunk_index=chunk_index,
                start_char=current_start,
                end_char=current_start + len(current_chunk),
                page_number=metadata.get('page_number') if metadata else None,
                section=metadata.get('section') if metadata else None
            )
            chunks.append(chunk_obj)

        logger.info(f"Split document '{doc_name}' into {len(chunks)} chunks")
        return chunks

    def _normalize_text(self, text: str) -> str:
        """Normalize whitespace and special characters while preserving paragraph breaks"""
        # Remove form feed, vertical tab, etc. but keep newlines
        text = re.sub(r'[\f\v]', '', text)
        # Normalize multiple newlines to double newline (paragraph break)
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Remove excessive spaces within lines but preserve newlines
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs"""
        # Split on double newlines (paragraph breaks) or page markers
        paragraphs = re.split(r'\n\s*\n|--- Page \d+ ---|(?:\n)+', text)
        # Filter out empty paragraphs and very short ones
        return [p.strip() + '\n\n' for p in paragraphs if p.strip() and len(p.strip()) > 20]

    def _get_overlap_text(self, text: str) -> str:
        """Extract overlap text from end of chunk"""
        if len(text) <= self.chunk_overlap:
            return text

        # Try to find sentence boundary within overlap region
        overlap_region = text[-self.chunk_overlap:]
        sentences = re.split(r'[.!?]\s+', overlap_region)

        # Return last complete sentence(s) within overlap
        if len(sentences) > 1:
            return sentences[-1]
        return overlap_region


class RecursiveCharacterSplitter:
    """
    Fallback splitter for documents without clear structure
    Recursively splits on different separators
    """

    def __init__(
        self,
        chunk_size: int = config.CHUNK_SIZE,
        chunk_overlap: int = config.CHUNK_OVERLAP
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", ". ", " ", ""]

    def split_text(
        self,
        text: str,
        doc_id: str,
        doc_name: str,
        metadata: Dict = None
    ) -> List[Chunk]:
        """Recursively split text using hierarchical separators"""
        chunks = []
        chunk_index = 0

        splits = self._split_recursive(text, self.separators)

        for i, split in enumerate(splits):
            chunk_obj = Chunk(
                text=split,
                chunk_id=f"{doc_id}_chunk_{chunk_index}",
                doc_id=doc_id,
                doc_name=doc_name,
                chunk_index=chunk_index,
                start_char=i * self.chunk_size,
                end_char=(i + 1) * self.chunk_size,
                page_number=metadata.get('page_number') if metadata else None
            )
            chunks.append(chunk_obj)
            chunk_index += 1

        return chunks

    def _split_recursive(self, text: str, separators: List[str]) -> List[str]:
        """Recursively split on separators"""
        if not separators:
            return [text]

        separator = separators[0]
        splits = text.split(separator)

        chunks = []
        current_chunk = ""

        for split in splits:
            if len(current_chunk) + len(split) > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = split
            else:
                current_chunk += separator + split if current_chunk else split

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
