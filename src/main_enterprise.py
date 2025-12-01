"""
Enterprise RAG System - Main Entry Point
Command-line interface for document ingestion and search
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import config
from src.utils.logger import setup_logger
from src.utils.llm_qa import generate_qa_answer
from src.vector_db.ingestion_pipeline import IngestionPipeline
from src.vector_db.search_engine import HybridSearchEngine
from src.vector_db.vector_store import VectorStore

logger = setup_logger(__name__)


class EnterpriseRAGCLI:
    """Command-line interface for the Enterprise RAG system"""

    def __init__(self):
        self.vector_store = VectorStore()
        self.ingestion_pipeline = IngestionPipeline(self.vector_store)
        self.search_engine = HybridSearchEngine(self.vector_store)

    def run(self):
        """Main CLI loop"""
        print("=" * 70)
        print("  ENTERPRISE RAG SYSTEM - Document Search & Retrieval")
        print("=" * 70)
        print(f"Data Directory: {config.DOCS_DIR}")
        print(f"Embedding Model: {config.EMBED_MODEL_NAME}")
        print("=" * 70)

        self._show_stats()

        while True:
            print("\nAvailable Commands:")
            print("  [I] Ingest documents from data/docs directory")
            print("  [F] Ingest a single file")
            print("  [S] Search (semantic)")
            print("  [H] Hybrid search (semantic + keyword)")
            print("  [K] Keyword search")
            print("  [T] Search with context")
            print("  [V] View statistics")
            print("  [L] List all documents")
            print("  [R] Remove a document")
            print("  [C] Clear all data")
            print("  [Q] Quit")
            print()

            choice = input("Enter command: ").strip().upper()

            try:
                if choice == 'I':
                    self._ingest_directory()
                elif choice == 'F':
                    self._ingest_file()
                elif choice == 'S':
                    self._search(mode='semantic')
                elif choice == 'H':
                    self._search(mode='hybrid')
                elif choice == 'K':
                    self._search(mode='keyword')
                elif choice == 'T':
                    self._search_with_context()
                elif choice == 'V':
                    self._show_stats()
                elif choice == 'L':
                    self._list_documents()
                elif choice == 'R':
                    self._remove_document()
                elif choice == 'C':
                    self._clear_all()
                elif choice == 'Q':
                    print("\nExiting... Goodbye!")
                    break
                else:
                    print("Invalid command. Please try again.")
            except KeyboardInterrupt:
                print("\n\nOperation cancelled.")
            except Exception as e:
                logger.error(f"Error executing command: {e}")
                print(f"\nError: {e}")

    def _ingest_directory(self):
        """Ingest all documents from configured directory"""
        print(f"\nIngesting documents from: {config.DOCS_DIR}")
        print("This may take a while depending on the number of documents...")

        stats = self.ingestion_pipeline.ingest_directory()

        print("\n--- Ingestion Results ---")
        print(f"Total files processed: {stats['total']}")
        print(f"Successfully ingested: {stats['success']}")
        print(f"Failed: {stats['failed']}")
        print(f"Skipped (up-to-date): {stats['skipped']}")

    def _ingest_file(self):
        """Ingest a single file"""
        file_path = input("\nEnter file path: ").strip()

        if not Path(file_path).exists():
            print(f"Error: File not found: {file_path}")
            return

        print(f"Ingesting: {file_path}")
        success = self.ingestion_pipeline.ingest_file(file_path)

        if success:
            print("File ingested successfully!")
        else:
            print("Failed to ingest file.")

    def _search(self, mode='hybrid'):
        """Perform search"""
        query = input("\nEnter search query: ").strip()

        if not query:
            print("Query cannot be empty.")
            return

        k = input(f"Number of results (default {config.DEFAULT_TOP_K}): ").strip()
        k = int(k) if k.isdigit() else config.DEFAULT_TOP_K

        # Ask if user wants full text or preview
        show_full = input("Show full text? (y/n, default y): ").strip().lower()
        show_full = show_full != 'n'

        # Ask if user wants to save results
        save_to_file = input("Save results to file? (y/n, default n): ").strip().lower()
        save_to_file = save_to_file == 'y'

        print(f"\nSearching ({mode} mode): '{query}'")
        print("-" * 70)

        results = self.search_engine.search(query, k=k, search_mode=mode)

        if not results:
            print("No results found.")
            return

        # Prepare output
        output_lines = []
        output_lines.append(f"\n{'='*70}")
        output_lines.append(f"SEARCH RESULTS FOR: '{query}'")
        output_lines.append(f"Search Mode: {mode.upper()}")
        output_lines.append(f"Total Results: {len(results)}")
        output_lines.append(f"{'='*70}\n")

        for i, result in enumerate(results, 1):
            output_lines.append(f"\n{'─'*70}")
            output_lines.append(f"[RESULT {i}/{len(results)}]")
            output_lines.append(f"{'─'*70}")
            output_lines.append(f"Document: {result.chunk_metadata.doc_name}")
            output_lines.append(f"Doc ID: {result.chunk_metadata.doc_id}")
            if result.chunk_metadata.page_number:
                output_lines.append(f"Page Number: {result.chunk_metadata.page_number}")
            output_lines.append(f"Chunk Index: {result.chunk_metadata.chunk_index}")
            output_lines.append(f"Chunk ID: {result.chunk_metadata.chunk_id}")
            output_lines.append(f"\nScores:")
            output_lines.append(f"  - Semantic Score: {result.semantic_score:.4f}")
            output_lines.append(f"  - Keyword Score: {result.keyword_score:.4f}")
            output_lines.append(f"  - Hybrid Score: {result.hybrid_score:.4f}")
            output_lines.append(f"\n--- MATCHED CHUNK ---")

            if show_full:
                # Show complete text with word wrapping
                text = result.chunk_metadata.text
                output_lines.append(text)
            else:
                # Show preview
                output_lines.append(result.chunk_metadata.text[:500] + "...")

            output_lines.append("")

        output_lines.append(f"\n{'='*70}")
        output_lines.append(f"END OF RESULTS ({len(results)} total)")
        output_lines.append(f"{'='*70}\n")

        # Print to console
        output_text = "\n".join(output_lines)
        print(output_text)

        # Save to file if requested
        if save_to_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"search_results_{timestamp}.txt"
            filepath = config.DATA_DIR / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(output_text)
            print(f"\n✓ Results saved to: {filepath}")

        # Generate LLM Q&A answer if enabled
        if config.USE_LLM_QA and results:
            self._generate_llm_answer(query, results, save_to_file)

    def _search_with_context(self):
        """Search with surrounding context"""
        query = input("\nEnter search query: ").strip()

        if not query:
            print("Query cannot be empty.")
            return

        k = input(f"Number of results (default {config.DEFAULT_TOP_K}): ").strip()
        k = int(k) if k.isdigit() else config.DEFAULT_TOP_K

        context_window = input("Context window (chunks before/after, default 1): ").strip()
        context_window = int(context_window) if context_window.isdigit() else 1

        # Ask if user wants to save results
        save_to_file = input("Save results to file? (y/n, default n): ").strip().lower()
        save_to_file = save_to_file == 'y'

        print(f"\nSearching with context: '{query}'")
        print("-" * 70)

        results = self.search_engine.search_with_context(
            query,
            k=k,
            context_window=context_window
        )

        if not results:
            print("No results found.")
            return

        # Prepare output
        output_lines = []
        output_lines.append(f"\n{'='*70}")
        output_lines.append(f"CONTEXT SEARCH RESULTS FOR: '{query}'")
        output_lines.append(f"Context Window: ±{context_window} chunks")
        output_lines.append(f"Total Results: {len(results)}")
        output_lines.append(f"{'='*70}\n")

        for i, result in enumerate(results, 1):
            output_lines.append(f"\n{'─'*70}")
            output_lines.append(f"[RESULT {i}/{len(results)}]")
            output_lines.append(f"{'─'*70}")
            output_lines.append(f"Document: {result['doc_name']}")
            output_lines.append(f"Doc ID: {result['doc_id']}")
            if result.get('page_number'):
                output_lines.append(f"Page Number: {result['page_number']}")
            output_lines.append(f"Hybrid Score: {result['hybrid_score']:.4f}")
            output_lines.append("")

            # Show context before
            before_ctx = [c for c in result.get('context', []) if c['position'] == 'before']
            if before_ctx:
                output_lines.append("┌─ CONTEXT BEFORE (Previous Chunks) ─────────────────────")
                for ctx in sorted(before_ctx, key=lambda x: x['chunk_index']):
                    output_lines.append(f"│ [Chunk {ctx['chunk_index']}]")
                    output_lines.append(f"│ {ctx['text']}")
                    output_lines.append("│")
                output_lines.append("└────────────────────────────────────────────────────────")
                output_lines.append("")

            # Show main chunk
            output_lines.append("╔═ MATCHED CHUNK (Your Search Result) ═══════════════════")
            output_lines.append(f"║ [Chunk {result.get('chunk_index', 'N/A')}]")
            output_lines.append(f"║ {result['text']}")
            output_lines.append("╚════════════════════════════════════════════════════════")
            output_lines.append("")

            # Show context after
            after_ctx = [c for c in result.get('context', []) if c['position'] == 'after']
            if after_ctx:
                output_lines.append("┌─ CONTEXT AFTER (Following Chunks) ─────────────────────")
                for ctx in sorted(after_ctx, key=lambda x: x['chunk_index']):
                    output_lines.append(f"│ [Chunk {ctx['chunk_index']}]")
                    output_lines.append(f"│ {ctx['text']}")
                    output_lines.append("│")
                output_lines.append("└────────────────────────────────────────────────────────")

            output_lines.append("")

        output_lines.append(f"\n{'='*70}")
        output_lines.append(f"END OF CONTEXT SEARCH ({len(results)} total)")
        output_lines.append(f"{'='*70}\n")

        # Print to console
        output_text = "\n".join(output_lines)
        print(output_text)

        # Save to file if requested
        if save_to_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"context_search_{timestamp}.txt"
            filepath = config.DATA_DIR / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(output_text)
            print(f"\n✓ Results saved to: {filepath}")

        # Generate LLM Q&A answer if enabled
        if config.USE_LLM_QA and results:
            self._generate_llm_answer_from_context(query, results, save_to_file)

    def _generate_llm_answer(self, query: str, results: list, save_to_file: bool = False):
        """Generate LLM answer based on search results"""
        print("\n" + "=" * 70)
        print("  LLM-POWERED Q&A (Showcasing RAG Accuracy)")
        print("=" * 70)
        print("\nAnalyzing retrieved chunks with Gemini AI...")
        print(f"Query: \"{query}\"")
        print(f"Analyzing {len(results)} retrieved chunks...\n")

        try:
            # Extract chunk texts from results
            chunks = [result.chunk_metadata.text for result in results]

            # Generate answer using Gemini
            answer = generate_qa_answer(query, chunks)

            if answer:
                print("-" * 70)
                print("LLM ANSWER:")
                print("-" * 70)
                print(answer)
                print("\n" + "=" * 70)
                print("END OF LLM ANSWER")
                print("=" * 70 + "\n")

                # Save LLM answer to file if requested
                if save_to_file:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"llm_answer_{timestamp}.txt"
                    filepath = config.DATA_DIR / filename

                    llm_output = f"""{'='*70}
LLM-POWERED Q&A - RAG System Answer
{'='*70}

Query: "{query}"
Number of chunks analyzed: {len(results)}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{'='*70}
LLM ANSWER
{'='*70}

{answer}

{'='*70}
END OF LLM ANSWER
{'='*70}
"""
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(llm_output)
                    print(f"✓ LLM answer saved to: {filepath}\n")
            else:
                print("⚠ Could not generate LLM answer. Check logs for details.\n")

        except Exception as e:
            logger.error(f"Error generating LLM answer: {e}")
            print(f"⚠ Error generating LLM answer: {e}\n")

    def _generate_llm_answer_from_context(self, query: str, results: list, save_to_file: bool = False):
        """Generate LLM answer based on context search results"""
        print("\n" + "=" * 70)
        print("  LLM-POWERED Q&A (Showcasing RAG Accuracy)")
        print("=" * 70)
        print("\nAnalyzing retrieved chunks with context using Gemini AI...")
        print(f"Query: \"{query}\"")
        print(f"Analyzing {len(results)} retrieved chunks with context...\n")

        try:
            # Extract all text from context results (main chunk + context)
            all_chunks = []
            for result in results:
                # Add context before
                for ctx in result.get('context', []):
                    if ctx['position'] == 'before':
                        all_chunks.append(ctx['text'])

                # Add main chunk
                all_chunks.append(result['text'])

                # Add context after
                for ctx in result.get('context', []):
                    if ctx['position'] == 'after':
                        all_chunks.append(ctx['text'])

            # Generate answer using Gemini
            answer = generate_qa_answer(query, all_chunks)

            if answer:
                print("-" * 70)
                print("LLM ANSWER:")
                print("-" * 70)
                print(answer)
                print("\n" + "=" * 70)
                print("END OF LLM ANSWER")
                print("=" * 70 + "\n")

                # Save LLM answer to file if requested
                if save_to_file:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"llm_answer_context_{timestamp}.txt"
                    filepath = config.DATA_DIR / filename

                    llm_output = f"""{'='*70}
LLM-POWERED Q&A - RAG System Answer (With Context)
{'='*70}

Query: "{query}"
Number of result groups analyzed: {len(results)}
Total chunks (including context): {len(all_chunks)}
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{'='*70}
LLM ANSWER
{'='*70}

{answer}

{'='*70}
END OF LLM ANSWER
{'='*70}
"""
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(llm_output)
                    print(f"✓ LLM answer saved to: {filepath}\n")
            else:
                print("⚠ Could not generate LLM answer. Check logs for details.\n")

        except Exception as e:
            logger.error(f"Error generating LLM answer: {e}")
            print(f"⚠ Error generating LLM answer: {e}\n")

    def _show_stats(self):
        """Display vector store statistics"""
        stats = self.ingestion_pipeline.get_stats()

        print("\n" + "=" * 70)
        print("  VECTOR STORE STATISTICS")
        print("=" * 70)
        print(f"Total Documents: {stats['total_documents']}")
        print(f"Total Chunks: {stats['total_chunks']}")
        print(f"Total Vectors: {stats['total_vectors']}")
        print(f"Embedding Dimension: {stats['embedding_dimension']}")
        print("=" * 70)

    def _list_documents(self):
        """List all ingested documents"""
        stats = self.ingestion_pipeline.get_stats()

        if not stats['documents']:
            print("\nNo documents in the system.")
            return

        print("\n" + "=" * 70)
        print("  INGESTED DOCUMENTS")
        print("=" * 70)

        for i, doc in enumerate(stats['documents'], 1):
            print(f"\n[{i}] {doc['filename']}")
            print(f"    Doc ID: {doc['doc_id']}")
            print(f"    Chunks: {doc['num_chunks']}")
            print(f"    Ingested: {doc['ingested_at']}")

        print("\n" + "=" * 70)

    def _remove_document(self):
        """Remove a document from the system"""
        self._list_documents()

        doc_id = input("\nEnter document ID to remove: ").strip()

        if not doc_id:
            print("Document ID cannot be empty.")
            return

        confirm = input(f"Are you sure you want to remove '{doc_id}'? (yes/no): ").strip().lower()

        if confirm != 'yes':
            print("Removal cancelled.")
            return

        print(f"\nRemoving document: {doc_id}")
        success = self.ingestion_pipeline.remove_document(doc_id)

        if success:
            print("Document removed successfully!")
        else:
            print("Failed to remove document.")

    def _clear_all(self):
        """Clear all data"""
        confirm = input("\nWARNING: This will delete ALL data. Type 'DELETE ALL' to confirm: ").strip()

        if confirm != 'DELETE ALL':
            print("Clear operation cancelled.")
            return

        print("\nClearing all data...")
        self.ingestion_pipeline.clear_all()
        print("All data cleared!")


def main():
    """Main entry point"""
    try:
        cli = EnterpriseRAGCLI()
        cli.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\nFatal Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
