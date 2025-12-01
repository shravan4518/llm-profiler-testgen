"""
Enterprise RAG Configuration
Centralized configuration for the RAG system with environment variable support
"""
import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = DATA_DIR / "docs"
INDEX_DIR = DATA_DIR / "faiss_index"
LOGS_DIR = DATA_DIR / "logs"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"

# Ensure directories exist
for directory in [DATA_DIR, DOCS_DIR, INDEX_DIR, LOGS_DIR, EMBEDDINGS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# FAISS Index Configuration
FAISS_INDEX_PATH = INDEX_DIR / "faiss_index.bin"
CHUNK_METADATA_PATH = INDEX_DIR / "chunk_metadata.pkl"
DOC_REGISTRY_PATH = INDEX_DIR / "document_registry.pkl"

# Embedding Configuration
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "all-MiniLM-L6-v2")
EMBED_DIM = 384  # Dimension for all-MiniLM-L6-v2
EMBED_BATCH_SIZE = 32  # Batch size for encoding

# Chunking Configuration
CHUNK_SIZE = 1000  # Characters per chunk (increased from 512)
CHUNK_OVERLAP = 200  # Overlap between chunks to maintain context
MIN_CHUNK_SIZE = 100  # Minimum viable chunk size

# Supported file types
SUPPORTED_FORMATS = [".txt", ".pdf", ".docx", ".md", ".json"]

# Search Configuration
DEFAULT_TOP_K = 5  # Number of results to return
SIMILARITY_THRESHOLD = 0.7  # Minimum similarity score (0-1)

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = LOGS_DIR / "rag_system.log"

# Performance Configuration
USE_GPU = False  # Set to True if GPU available
MAX_WORKERS = 4  # For parallel processing

# Document Processing
EXTRACT_METADATA = True  # Extract doc metadata (title, author, etc.)      
ENABLE_OCR = False  # Enable OCR for scanned PDFs (requires tesseract)

# Azure OpenAI Configuration (Production LLM)
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "YOUR_ENDPOINT_HERE") 
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "YOUR_API_KEY_HERE")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1-nano")
AZURE_OPENAI_API_VERSION = "2024-08-01-preview"

# LLM Configuration for Test Case Generation
LLM_TEMPERATURE = 0.7  # Balanced creativity for diverse test cases
LLM_MAX_TOKENS = 4096  # Maximum tokens for comprehensive test generation
LLM_TOP_P = 0.9  # Nucleus sampling for quality

# CrewAI Agent Configuration
ENABLE_CREWAI = True  # Enable multi-agent orchestration
AGENT_VERBOSE = True  # Enable detailed agent logging
MAX_ITERATIONS = 3  # Maximum agent iterations for refinement

# Test Case Generation Configuration
MIN_TEST_CASES_PER_FEATURE = 10  # Minimum test cases to generate
COVERAGE_TYPES = ["positive", "negative", "boundary", "integration", "security", "performance"]
OUTPUT_FORMATS = ["json", "markdown", "excel"]  # Supported output formats

# Multimodal Image Processing (Disabled - was for Gemini)
ENABLE_IMAGE_PROCESSING = False  # Disabled (use Azure GPT-4 Vision if needed)
