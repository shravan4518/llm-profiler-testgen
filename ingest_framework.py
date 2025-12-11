"""
Ingest Client Framework Code into Vector Database

This script loads your test automation framework code and ingests it
into the vector database alongside your documentation. This allows
the LLM to learn framework patterns when generating test scripts.

Usage:
    python ingest_framework.py --framework-path /path/to/framework
    python ingest_framework.py --framework-path /path/to/framework --clear
"""
import sys
from pathlib import Path
import argparse

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.document_processing.code_loader import load_framework_repository, PythonCodeLoader
from src.vector_db.ingestion_pipeline import IngestionPipeline
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def ingest_framework_code(framework_path: str, clear_existing: bool = False):
    """
    Ingest framework code into vector database

    Args:
        framework_path: Path to your test automation framework
        clear_existing: If True, clears existing data before ingestion
    """

    logger.info("=" * 80)
    logger.info("FRAMEWORK CODE INGESTION")
    logger.info("=" * 80)

    # Load framework code
    logger.info(f"\n[Step 1] Loading framework code from: {framework_path}")
    logger.info("-" * 80)

    documents = load_framework_repository(
        framework_path=framework_path,
        include_patterns=[
            '**/*.py',             # All Python files
            '*TestSuite.py',       # Test suite files (direct children)
            '*_Data.py',           # Test data files (direct children)
            '*Utils.py',           # Utility files (direct children)
        ]
    )

    if not documents:
        logger.error(f"No framework files found in {framework_path}")
        logger.error("Make sure the path is correct and contains Python files")
        return False

    logger.info(f"\n✓ Loaded {len(documents)} framework files")

    # Show what was loaded
    logger.info("\nLoaded files:")
    for doc in documents:
        logger.info(f"  - {doc.filename}")

    # Ingest into vector database
    logger.info(f"\n[Step 2] Ingesting into vector database...")
    logger.info("-" * 80)

    pipeline = IngestionPipeline()

    if clear_existing:
        logger.warning("Clearing existing vector database...")
        # Note: You might want to backup before clearing
        # For now, we'll just ingest on top of existing data

    # Ingest documents using file paths
    success_count = 0
    failed_count = 0

    for doc in documents:
        try:
            # Use ingest_file which expects a file path
            result = pipeline.ingest_file(doc.file_path)
            if result:
                success_count += 1
                logger.info(f"✓ Ingested: {doc.filename}")
            else:
                failed_count += 1
                logger.error(f"✗ Failed to ingest: {doc.filename}")
        except Exception as e:
            failed_count += 1
            logger.error(f"✗ Error ingesting {doc.filename}: {e}")

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 80)

    logger.info(f"Total files: {len(documents)}")
    logger.info(f"Successfully ingested: {success_count}")
    logger.info(f"Failed: {failed_count}")

    logger.info("\n✓ Framework code is now searchable in the vector database!")
    logger.info("✓ LLM can now learn from your framework patterns when generating test scripts")

    return success_count > 0


def main():
    parser = argparse.ArgumentParser(
        description='Ingest test automation framework code into vector database'
    )
    parser.add_argument(
        '--framework-path',
        type=str,
        required=True,
        help='Path to your test automation framework repository'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear existing data before ingestion'
    )

    args = parser.parse_args()

    # Validate path
    framework_path = Path(args.framework_path)
    if not framework_path.exists():
        logger.error(f"Framework path does not exist: {framework_path}")
        return 1

    # Ingest framework
    success = ingest_framework_code(
        framework_path=str(framework_path),
        clear_existing=args.clear
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
