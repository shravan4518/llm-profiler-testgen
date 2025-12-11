# Image Processing Guide

## Overview

The system now supports **multimodal RAG** - extracting and understanding images from PDF documents during ingestion. Images are analyzed using **Azure OpenAI Vision (GPT-4o)** and converted to searchable text descriptions that are embedded alongside the document text.

This allows you to ask questions about diagrams, screenshots, charts, and architecture diagrams in your documentation!

---

## Current Status

✅ **Image processing is configured but DISABLED by default**

The infrastructure is ready to use. To enable:
1. Set `ENABLE_IMAGE_PROCESSING = True` in `config.py`
2. Configure vision model credentials (see below)
3. Re-ingest your documents

---

## Configuration

### Enable Image Processing

Edit [`config.py`](../config.py):

```python
# ============================================================================
# MULTIMODAL IMAGE PROCESSING CONFIGURATION
# ============================================================================

ENABLE_IMAGE_PROCESSING = True  # Set to True to enable

# Vision LLM Configuration
VISION_ENDPOINT = "https://your-endpoint.openai.azure.com/"  # Your Azure endpoint
VISION_API_KEY = "your-api-key-here"                         # Your API key
VISION_DEPLOYMENT = "gpt-4o"                                 # Vision model deployment name
VISION_API_VERSION = "2024-02-15-preview"                    # API version

# Image Processing Parameters
IMAGE_MIN_SIZE = 100          # Min pixels (filters out small icons)
MAX_IMAGES_PER_PAGE = 10      # Max images per PDF page
IMAGE_DESCRIPTION_MAX_TOKENS = 500  # Max tokens per description
```

### Separate Vision Model (Optional)

You can use a **different Azure deployment** for vision tasks:

```python
# Use same credentials as text generation (default)
VISION_ENDPOINT = AZURE_OPENAI_ENDPOINT
VISION_API_KEY = AZURE_OPENAI_API_KEY
VISION_DEPLOYMENT = "gpt-4o"

# OR use completely separate vision deployment
VISION_ENDPOINT = "https://vision-endpoint.openai.azure.com/"
VISION_API_KEY = "different-api-key"
VISION_DEPLOYMENT = "my-vision-model"
```

### Environment Variables (Recommended)

For security, use environment variables:

```bash
export VISION_ENDPOINT="https://your-endpoint.openai.azure.com/"
export VISION_API_KEY="your-key-here"
export VISION_DEPLOYMENT="gpt-4o"
```

---

## Supported Vision Models

| Model | Recommended | Notes |
|-------|-------------|-------|
| **gpt-4o** | ✅ Yes | Best balance of speed, cost, and quality |
| **gpt-4-turbo-vision** | ✅ Yes | Good quality, faster |
| **gpt-4-vision** | ⚠️ OK | Slower, more expensive |

**Recommendation**: Use `gpt-4o` for production

---

## How It Works

### 1. During Document Ingestion

When you ingest a PDF:

```python
from src.vector_db.ingestion_pipeline import DocumentIngestionPipeline

pipeline = DocumentIngestionPipeline()
pipeline.ingest_documents("path/to/your/docs")
```

The system automatically:
1. **Extracts images** from each PDF page
2. **Filters images** by size (skips small icons/logos)
3. **Analyzes each image** using Azure Vision API
4. **Generates descriptions** like:
   ```
   [IMAGE DESCRIPTION]
   This is an architecture diagram showing three main components:
   - Frontend (React) connecting to API Gateway
   - Backend Services (Node.js microservices)
   - Database layer (PostgreSQL and Redis)
   The diagram shows REST API connections between components...
   ```
5. **Embeds descriptions** alongside text chunks
6. **Stores in vector database** for semantic search

### 2. During Test Case Generation

When you generate test cases:

```python
result = generator.generate(user_prompt="API Gateway diagram")
```

The RAG system:
1. **Searches both text AND image descriptions**
2. **Retrieves relevant context** including image descriptions
3. **LLM uses image content** to generate more accurate test cases

---

## Example: Before vs After

### Before (Text Only)
**User**: "Generate test cases for the database migration process"

**RAG Context**: "The profiler database can be exported and imported..."

**Result**: Generic test cases based only on text

### After (With Image Understanding)
**User**: "Generate test cases for the database migration process"

**RAG Context**:
```
The profiler database can be exported and imported...

[IMAGE DESCRIPTION]
This is a flowchart diagram showing the database migration process:
- Step 1: Export device database (binary format)
- Step 2: Backup verification with checksum
- Step 3: Upgrade software version
- Step 4: Import database with validation
- Step 5: Session invalidation and re-authentication
The diagram shows error handling paths at each step...
```

**Result**: Test cases covering the specific steps shown in the diagram!

---

## Image Processing Statistics

After ingestion, check the logs:

```
INFO - Page 5: Extracted 3 images
INFO - Analyzing 3 images from page 5...
INFO - Generated image description (287 chars)
INFO - Page 5: Generated 3 image descriptions
INFO - Image processing complete: 12 descriptions generated
INFO - Enhanced content with 12 image descriptions
```

---

## Cost Considerations

### Pricing (Azure GPT-4o Vision)
- **Input**: ~$0.005 per image (for 500-token description)
- **Per document**: Varies by image count
  - 10 images = ~$0.05
  - 50 images = ~$0.25
  - 100 images = ~$0.50

### Cost Control

**1. Filter small images:**
```python
IMAGE_MIN_SIZE = 200  # Increase to skip more images
```

**2. Limit images per page:**
```python
MAX_IMAGES_PER_PAGE = 5  # Reduce if PDFs have many diagrams
```

**3. Process selectively:**
Only enable for documents with important diagrams

---

## Testing Image Processing

### Test Script

Create `test_image_processing.py`:

```python
from src.document_processing.loaders import PDFLoader
import config

# Enable image processing
config.ENABLE_IMAGE_PROCESSING = True

# Load PDF with images
doc = PDFLoader.load("path/to/your/document.pdf")

# Check if images were processed
if 'has_images' in doc.metadata:
    print(f"✅ Processed {doc.metadata['image_count']} images")
    print(f"Content length: {len(doc.content)} chars")
else:
    print("❌ No images processed")
```

### Verify in Vector Database

```python
from src.vector_db.search_engine import HybridSearchEngine

search = HybridSearchEngine()
results = search.search("diagram architecture", k=5)

for result in results:
    if "[IMAGE DESCRIPTION]" in result.text:
        print(f"✅ Found image description in: {result.source}")
```

---

## Troubleshooting

### Issue: No images being processed

**Check 1**: Is it enabled?
```python
# config.py
ENABLE_IMAGE_PROCESSING = True  # Must be True
```

**Check 2**: Are credentials correct?
```python
# Check logs for:
# "Azure Vision LLM initialized: gpt-4o"
```

**Check 3**: Are images large enough?
```python
IMAGE_MIN_SIZE = 50  # Lower threshold for testing
```

### Issue: Vision API errors

**Error**: "Deployment not found"
```python
# Fix: Check your deployment name in Azure portal
VISION_DEPLOYMENT = "your-actual-deployment-name"
```

**Error**: "Rate limit exceeded"
```python
# The system automatically retries with backoff
# But you can reduce concurrent processing:
MAX_IMAGES_PER_PAGE = 3  # Process fewer images
```

### Issue: Poor image descriptions

**Problem**: Descriptions are too generic

**Solution**: The prompt is in `image_processor.py:144-152`. You can customize:
```python
prompt = """Describe this PROFILER documentation image. Include:
- Specific profiler components (collectors, DAL, REST API)
- Configuration settings and values
- Database schemas or structures
- Network architecture and connections
..."""
```

---

## Advanced: Custom Image Processing

### Process specific image types

Edit [`image_processor.py`](../src/document_processing/image_processor.py):

```python
def should_process_image(self, image: Image.Image) -> bool:
    """Custom logic to filter images"""
    width, height = image.size

    # Skip very wide/thin images (likely headers/footers)
    aspect_ratio = width / height
    if aspect_ratio > 5 or aspect_ratio < 0.2:
        return False

    # Skip grayscale images (likely text screenshots)
    if image.mode == "L":
        return False

    return True
```

### Add OCR for text in images

```python
import pytesseract

def extract_text_from_image(self, image: Image.Image) -> str:
    """Extract text using OCR"""
    text = pytesseract.image_to_string(image)
    return text.strip()
```

---

## Migration from Gemini

The system was previously configured for Google Gemini Vision. It has been migrated to Azure OpenAI Vision.

**What changed:**
- ❌ Removed: `google-generativeai` dependency
- ✅ Added: Azure OpenAI Vision support
- ✅ Added: Configurable vision endpoint/deployment
- ✅ Same functionality, better integration with existing Azure setup

**Old backup available at:**
`src/document_processing/image_processor_backup.py`

---

## Summary

**Current State:**
- ✅ Image processing infrastructure is ready
- ✅ Azure OpenAI Vision integration complete
- ⚠️ Disabled by default (set `ENABLE_IMAGE_PROCESSING = True` to use)

**To Enable:**
1. Set `ENABLE_IMAGE_PROCESSING = True` in config.py
2. Configure vision credentials
3. Re-ingest documents

**Benefits:**
- Understand diagrams, screenshots, charts
- Generate test cases based on visual documentation
- Comprehensive knowledge base including visual information

**Costs:**
- ~$0.005 per image
- ~$0.50 per 100-image document
- Control with `IMAGE_MIN_SIZE` and `MAX_IMAGES_PER_PAGE`
