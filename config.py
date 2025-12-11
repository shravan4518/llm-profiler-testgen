"""
Enterprise RAG Configuration
Centralized configuration for the RAG system with environment variable support

IMPORTANT: API keys and sensitive configuration are stored in .env file
           Copy .env.example to .env and add your actual API keys
           The .env file is excluded from Git for security
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

# ============================================================================
# AZURE OPENAI CONFIGURATION - Easy Model Switching
# ============================================================================
#
# Supported Models:
#   - "gpt-4-1-nano"     : GPT-4.1 Nano (fast, cheap, uses max_tokens)
#   - "gpt-4o"           : GPT-4 Optimized (balanced)
#   - "gpt-5.1-2"        : GPT-5.1 (latest, uses max_completion_tokens)
#   - "gpt-5-preview"    : GPT-5 Preview
#
# To switch models: Just change AZURE_OPENAI_DEPLOYMENT below
# The system automatically handles parameter compatibility
# ============================================================================

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")  # Default model
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")

# Validate required environment variables
if not AZURE_OPENAI_ENDPOINT or not AZURE_OPENAI_API_KEY:
    raise ValueError(
        "Missing required environment variables!\n"
        "Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in your .env file.\n"
        "See .env.example for template."
    )

# LLM Configuration for Test Case Generation
LLM_TEMPERATURE = 1.0  # Temperature (NOTE: GPT-5.1-2 only supports 1.0, GPT-4 supports 0.0-2.0)
LLM_MAX_TOKENS = 16000  # Maximum tokens for comprehensive test generation (auto-converted for GPT-5+)
                        # GPT-5 needs higher limits - 8000 was causing truncation with long prompts
LLM_TOP_P = 0.9  # Nucleus sampling for quality (not used for GPT-5.1-2)

# CrewAI Agent Configuration
ENABLE_CREWAI = True  # Enable multi-agent orchestration
AGENT_VERBOSE = True  # Enable detailed agent logging
MAX_ITERATIONS = 3  # Maximum agent iterations for refinement

# Test Case Generation Configuration
MIN_TEST_CASES_PER_FEATURE = 10  # Minimum test cases to generate
COVERAGE_TYPES = ["positive", "negative", "boundary", "integration", "security", "performance"]
OUTPUT_FORMATS = ["json", "markdown", "excel"]  # Supported output formats

# ============================================================================
# MULTIMODAL IMAGE PROCESSING CONFIGURATION
# ============================================================================
# Enable image extraction and description during document ingestion
# Images are analyzed using Vision LLM and descriptions are added to knowledge base
# ============================================================================

ENABLE_IMAGE_PROCESSING = True  # Set to True to enable image understanding

# Vision LLM Configuration for Image Analysis
# Separate endpoint/deployment allows using different model for vision tasks
VISION_ENDPOINT = os.getenv("VISION_ENDPOINT", AZURE_OPENAI_ENDPOINT)  # Defaults to same as text LLM
VISION_API_KEY = os.getenv("VISION_API_KEY", AZURE_OPENAI_API_KEY)      # Defaults to same as text LLM
VISION_DEPLOYMENT = os.getenv("VISION_DEPLOYMENT", "gpt-4o")             # Vision-capable model (gpt-4o, gpt-4-vision)
VISION_API_VERSION = os.getenv("VISION_API_VERSION", "2024-02-15-preview")  # API version for vision features

# Image Processing Parameters
IMAGE_MIN_SIZE = 100  # Minimum image size (pixels) to process (filters out icons/logos)
MAX_IMAGES_PER_PAGE = 10  # Maximum images to process per PDF page
IMAGE_DESCRIPTION_MAX_TOKENS = 500  # Max tokens for each image description