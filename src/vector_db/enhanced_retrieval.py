"""
Enhanced RAG Retrieval with Multi-Query Optimization
Implements advanced retrieval strategies for maximum context coverage
"""
import sys
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import config
from src.utils.logger import setup_logger
from src.vector_db.search_engine import HybridSearchEngine

logger = setup_logger(__name__)


class EnhancedRetrieval:
    """
    Enhanced retrieval engine with multi-query optimization
    and intelligent result aggregation
    """

    def __init__(self, search_engine: HybridSearchEngine):
        """
        Initialize enhanced retrieval

        Args:
            search_engine: Base hybrid search engine
        """
        self.search_engine = search_engine
        logger.info("Enhanced Retrieval initialized")

    def multi_query_retrieve(
        self,
        queries: List[str],
        top_k: int = 5,
        mode: str = 'hybrid'
    ) -> List[Dict]:
        """
        Retrieve results using multiple queries and aggregate intelligently

        Args:
            queries: List of search queries
            top_k: Results per query
            mode: Search mode (hybrid, semantic, keyword)

        Returns:
            Aggregated and deduplicated results
        """
        logger.info(f"Multi-query retrieval with {len(queries)} queries")

        all_results = []
        seen_chunks = set()

        for idx, query in enumerate(queries, 1):
            logger.debug(f"Query {idx}/{len(queries)}: {query[:50]}...")

            try:
                # Perform search
                results = self.search_engine.search(
                    query=query,
                    k=top_k,
                    search_mode=mode
                )

                # Add results with query tracking
                for result in results:
                    # Convert SearchResult to dict
                    result_dict = result.to_dict()
                    chunk_id = result_dict.get('chunk_id')

                    # Deduplicate by chunk_id
                    if chunk_id not in seen_chunks:
                        result_dict['query_source'] = query
                        result_dict['query_rank'] = idx
                        result_dict['file_path'] = result_dict.get('doc_name', '')
                        all_results.append(result_dict)
                        seen_chunks.add(chunk_id)

            except Exception as e:
                logger.error(f"Query {idx} failed: {e}")
                continue

        logger.info(f"Retrieved {len(all_results)} unique results from {len(queries)} queries")

        # Rerank results by relevance score
        ranked_results = self._rerank_results(all_results)

        # Return top results
        return ranked_results[:top_k * 2]  # Double the top_k for more context

    def _rerank_results(self, results: List[Dict]) -> List[Dict]:
        """
        Rerank results by combined relevance score

        Args:
            results: List of search results

        Returns:
            Reranked results
        """
        # Sort by score (descending) and query_rank (ascending)
        ranked = sorted(
            results,
            key=lambda x: (x.get('score', 0), -x.get('query_rank', 999)),
            reverse=True
        )

        return ranked

    def retrieve_with_context_expansion(
        self,
        query: str,
        top_k: int = 5,
        expand_neighbors: bool = True
    ) -> List[Dict]:
        """
        Retrieve results with context expansion (neighboring chunks)

        Args:
            query: Search query
            top_k: Number of top results
            expand_neighbors: Whether to include neighboring chunks

        Returns:
            Results with expanded context
        """
        logger.info(f"Context-expanded retrieval: {query[:50]}...")

        # Get initial results
        initial_results = self.search_engine.search(
            query=query,
            k=top_k,
            search_mode='hybrid'
        )

        if not expand_neighbors:
            # Convert to dicts
            return [r.to_dict() for r in initial_results]

        # Expand with neighboring chunks
        expanded_results = []
        seen_chunks = set()

        for result in initial_results:
            result_dict = result.to_dict()
            chunk_id = result_dict.get('chunk_id')
            file_path = result_dict.get('doc_name', '')

            # Add original chunk
            if chunk_id not in seen_chunks:
                result_dict['file_path'] = file_path
                expanded_results.append(result_dict)
                seen_chunks.add(chunk_id)

            # Get neighboring chunks from same document
            neighbors = self._get_neighbor_chunks(chunk_id, file_path)
            for neighbor in neighbors:
                neighbor_id = neighbor.get('chunk_id')
                if neighbor_id not in seen_chunks:
                    neighbor['is_context_expansion'] = True
                    expanded_results.append(neighbor)
                    seen_chunks.add(neighbor_id)

        logger.info(f"Expanded to {len(expanded_results)} chunks (from {len(initial_results)})")
        return expanded_results

    def _get_neighbor_chunks(
        self,
        chunk_id: int,
        file_path: str,
        window_size: int = 1
    ) -> List[Dict]:
        """
        Get neighboring chunks from the same document

        Args:
            chunk_id: Current chunk ID
            file_path: Document file path
            window_size: Number of chunks before/after

        Returns:
            List of neighboring chunks
        """
        try:
            # Get all chunks from the same document
            metadata_list = self.search_engine.vector_store.chunk_metadata

            neighbors = []
            for idx, metadata in enumerate(metadata_list):
                if metadata.get('file_path') == file_path:
                    # Check if within window
                    if abs(idx - chunk_id) <= window_size and idx != chunk_id:
                        neighbors.append({
                            'chunk_id': idx,
                            'text': metadata.get('text', ''),
                            'file_path': file_path,
                            'page_number': metadata.get('page_number'),
                            'score': 0.5  # Lower score for context chunks
                        })

            return neighbors

        except Exception as e:
            logger.error(f"Failed to get neighbor chunks: {e}")
            return []

    def adaptive_retrieve(
        self,
        queries: List[str],
        min_results: int = 10,
        max_results: int = 20
    ) -> List[Dict]:
        """
        Adaptive retrieval that dynamically adjusts based on result quality

        Args:
            queries: List of search queries
            min_results: Minimum number of results
            max_results: Maximum number of results

        Returns:
            Adaptively retrieved results
        """
        logger.info("Adaptive retrieval started")

        # Start with hybrid search
        results = self.multi_query_retrieve(
            queries=queries,
            top_k=5,
            mode='hybrid'
        )

        # If not enough results, try semantic search
        if len(results) < min_results:
            logger.info("Insufficient results, trying semantic search")
            semantic_results = self.multi_query_retrieve(
                queries=queries,
                top_k=5,
                mode='semantic'
            )

            # Merge results
            seen_chunks = {r.get('chunk_id') for r in results}
            for r in semantic_results:
                if r.get('chunk_id') not in seen_chunks:
                    results.append(r)
                    seen_chunks.add(r.get('chunk_id'))

        # Trim to max_results
        results = results[:max_results]

        logger.info(f"Adaptive retrieval complete: {len(results)} results")
        return results
