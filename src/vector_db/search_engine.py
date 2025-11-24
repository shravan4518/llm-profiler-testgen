"""
Advanced Search Engine with Hybrid Search Capabilities
Combines semantic search with keyword search for optimal retrieval
"""
import re
from typing import List, Dict, Tuple, Optional
from collections import Counter
import numpy as np
import config
from src.utils.logger import setup_logger
from src.vector_db.vector_store import VectorStore, ChunkMetadata

logger = setup_logger(__name__)


class SearchResult:
    """Represents a search result with scoring information"""

    def __init__(
        self,
        chunk_metadata: ChunkMetadata,
        semantic_score: float,
        keyword_score: float = 0.0,
        hybrid_score: float = 0.0
    ):
        self.chunk_metadata = chunk_metadata
        self.semantic_score = semantic_score
        self.keyword_score = keyword_score
        self.hybrid_score = hybrid_score

    def to_dict(self) -> Dict:
        """Convert to dictionary for display"""
        return {
            'doc_name': self.chunk_metadata.doc_name,
            'doc_id': self.chunk_metadata.doc_id,
            'chunk_id': self.chunk_metadata.chunk_id,
            'text': self.chunk_metadata.text,
            'page_number': self.chunk_metadata.page_number,
            'semantic_score': round(self.semantic_score, 4),
            'keyword_score': round(self.keyword_score, 4),
            'hybrid_score': round(self.hybrid_score, 4)
        }


class KeywordSearcher:
    """
    Keyword-based search using TF-IDF-like scoring
    Useful for exact term matching and technical queries
    """

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Tokenize text into words"""
        # Convert to lowercase and extract words
        words = re.findall(r'\b\w+\b', text.lower())
        return words

    @staticmethod
    def calculate_bm25_score(
        query_terms: List[str],
        document_text: str,
        k1: float = 1.5,
        b: float = 0.75,
        avg_doc_length: float = 500
    ) -> float:
        """
        Calculate BM25 score for keyword matching

        Args:
            query_terms: List of query terms
            document_text: Document text to score
            k1: BM25 parameter (term frequency saturation)
            b: BM25 parameter (length normalization)
            avg_doc_length: Average document length

        Returns:
            BM25 score
        """
        doc_terms = KeywordSearcher.tokenize(document_text)
        doc_length = len(doc_terms)
        doc_term_freq = Counter(doc_terms)

        score = 0.0
        for term in query_terms:
            if term in doc_term_freq:
                tf = doc_term_freq[term]
                # BM25 formula
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * (doc_length / avg_doc_length))
                score += numerator / denominator

        return score

    @staticmethod
    def search(
        query: str,
        chunks: Dict[int, ChunkMetadata],
        top_k: int = 20
    ) -> List[Tuple[ChunkMetadata, float]]:
        """
        Perform keyword search on chunks

        Args:
            query: Search query
            chunks: Dictionary of chunk metadata
            top_k: Number of results to return

        Returns:
            List of (ChunkMetadata, score) tuples
        """
        query_terms = KeywordSearcher.tokenize(query)

        if not query_terms:
            return []

        # Calculate avg document length
        avg_length = sum(len(KeywordSearcher.tokenize(c.text)) for c in chunks.values()) / len(chunks)

        # Score all chunks
        scores = []
        for chunk in chunks.values():
            score = KeywordSearcher.calculate_bm25_score(
                query_terms,
                chunk.text,
                avg_doc_length=avg_length
            )
            if score > 0:
                scores.append((chunk, score))

        # Sort by score and return top k
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class HybridSearchEngine:
    """
    Hybrid search combining semantic and keyword search
    Provides the best of both worlds for enterprise RAG
    """

    def __init__(
        self,
        vector_store: VectorStore = None,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ):
        """
        Initialize hybrid search engine

        Args:
            vector_store: VectorStore instance
            semantic_weight: Weight for semantic search (0-1)
            keyword_weight: Weight for keyword search (0-1)
        """
        self.vector_store = vector_store or VectorStore()
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        self.keyword_searcher = KeywordSearcher()

    def search(
        self,
        query: str,
        k: int = config.DEFAULT_TOP_K,
        search_mode: str = 'hybrid',
        score_threshold: float = None
    ) -> List[SearchResult]:
        """
        Perform search with specified mode

        Args:
            query: Search query
            k: Number of results
            search_mode: 'semantic', 'keyword', or 'hybrid'
            score_threshold: Minimum score threshold

        Returns:
            List of SearchResult objects
        """
        if search_mode == 'semantic':
            return self._semantic_search(query, k, score_threshold)
        elif search_mode == 'keyword':
            return self._keyword_search(query, k)
        else:  # hybrid
            return self._hybrid_search(query, k, score_threshold)

    def _semantic_search(
        self,
        query: str,
        k: int,
        score_threshold: float = None
    ) -> List[SearchResult]:
        """Perform semantic vector search"""
        results = self.vector_store.search(query, k * 2, score_threshold)

        search_results = []
        for chunk_meta, score in results[:k]:
            search_results.append(
                SearchResult(
                    chunk_metadata=chunk_meta,
                    semantic_score=score,
                    keyword_score=0.0,
                    hybrid_score=score
                )
            )

        logger.info(f"Semantic search returned {len(search_results)} results")
        return search_results

    def _keyword_search(self, query: str, k: int) -> List[SearchResult]:
        """Perform keyword search"""
        results = self.keyword_searcher.search(
            query,
            self.vector_store.chunk_metadata,
            top_k=k
        )

        search_results = []
        for chunk_meta, score in results:
            # Normalize keyword score to 0-1 range
            normalized_score = min(score / 10.0, 1.0)
            search_results.append(
                SearchResult(
                    chunk_metadata=chunk_meta,
                    semantic_score=0.0,
                    keyword_score=normalized_score,
                    hybrid_score=normalized_score
                )
            )

        logger.info(f"Keyword search returned {len(search_results)} results")
        return search_results

    def _hybrid_search(
        self,
        query: str,
        k: int,
        score_threshold: float = None
    ) -> List[SearchResult]:
        """
        Perform hybrid search combining semantic and keyword methods

        Args:
            query: Search query
            k: Number of results
            score_threshold: Minimum score threshold

        Returns:
            List of SearchResult objects ranked by hybrid score
        """
        # Get semantic results (more results to ensure coverage)
        semantic_results = self.vector_store.search(query, k * 3, score_threshold)

        # Get keyword results
        keyword_results = self.keyword_searcher.search(
            query,
            self.vector_store.chunk_metadata,
            top_k=k * 3
        )

        # Create lookup dictionaries
        semantic_scores = {meta.chunk_id: score for meta, score in semantic_results}
        keyword_scores = {meta.chunk_id: score for meta, score in keyword_results}

        # Combine results
        all_chunk_ids = set(semantic_scores.keys()) | set(keyword_scores.keys())

        hybrid_results = []
        for chunk_id in all_chunk_ids:
            # Get chunk metadata (from either result set)
            chunk_meta = None
            for meta, _ in semantic_results:
                if meta.chunk_id == chunk_id:
                    chunk_meta = meta
                    break
            if chunk_meta is None:
                for meta, _ in keyword_results:
                    if meta.chunk_id == chunk_id:
                        chunk_meta = meta
                        break

            if chunk_meta is None:
                continue

            # Get individual scores
            sem_score = semantic_scores.get(chunk_id, 0.0)
            kw_score = keyword_scores.get(chunk_id, 0.0)

            # Normalize keyword score
            kw_score_norm = min(kw_score / 10.0, 1.0)

            # Calculate hybrid score
            hybrid_score = (
                self.semantic_weight * sem_score +
                self.keyword_weight * kw_score_norm
            )

            hybrid_results.append(
                SearchResult(
                    chunk_metadata=chunk_meta,
                    semantic_score=sem_score,
                    keyword_score=kw_score_norm,
                    hybrid_score=hybrid_score
                )
            )

        # Sort by hybrid score
        hybrid_results.sort(key=lambda x: x.hybrid_score, reverse=True)

        logger.info(f"Hybrid search returned {len(hybrid_results[:k])} results")
        return hybrid_results[:k]

    def search_with_context(
        self,
        query: str,
        k: int = config.DEFAULT_TOP_K,
        context_window: int = 1
    ) -> List[Dict]:
        """
        Search with surrounding context chunks

        Args:
            query: Search query
            k: Number of primary results
            context_window: Number of surrounding chunks to include

        Returns:
            List of results with context
        """
        results = self.search(query, k, search_mode='hybrid')

        results_with_context = []
        for result in results:
            # Get surrounding chunks
            doc_id = result.chunk_metadata.doc_id
            chunk_idx = result.chunk_metadata.chunk_index

            context_chunks = []
            for i in range(-context_window, context_window + 1):
                if i == 0:
                    continue
                target_idx = chunk_idx + i
                # Find chunk with matching doc_id and chunk_index
                for meta in self.vector_store.chunk_metadata.values():
                    if meta.doc_id == doc_id and meta.chunk_index == target_idx:
                        context_chunks.append({
                            'position': 'before' if i < 0 else 'after',
                            'text': meta.text,
                            'chunk_index': meta.chunk_index
                        })
                        break

            result_dict = result.to_dict()
            result_dict['context'] = context_chunks
            results_with_context.append(result_dict)

        return results_with_context
