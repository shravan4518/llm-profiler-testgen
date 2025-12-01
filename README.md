# Enterprise RAG System for Test Case Generation

> Advanced Retrieval-Augmented Generation system with LLM-powered Q&A for document search and AI agent integration

## 🎯 Project Overview

This enterprise-grade RAG system enables intelligent document search and retrieval to support AI agents in generating test cases for automation and profiling workflows. It processes admin guides, API documentation, and product workflows to provide semantic and keyword-based search capabilities.

## 🚀 Quick Start

### 1. Activate Environment
```bash
venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Add Your Documents
Place documents in `data/docs/`:
- Supported formats: PDF, TXT, MD, JSON

### 4. Run the System
```bash
python src/main_enterprise.py
```

### 5. Basic Usage
```
[I] Ingest documents     - Process all docs in data/docs/
[H] Hybrid search        - Best for most queries
[T] Context search       - Get surrounding chunks
[V] View statistics      - Check system status
[Q] Quit
```

## 📁 Project Structure

```
POC/
├── config.py                          # Central configuration
├── requirements.txt                   # Python dependencies
├── README.md                          # This file
│
├── Documentation/
│   ├── ENTERPRISE_RAG_DOCUMENTATION.txt   # Complete guide
│   ├── QUICK_START.txt                    # Quick reference
│   ├── SEARCH_OUTPUT_GUIDE.txt            # Search usage
│   └── SYSTEM_SUMMARY.txt                 # Architecture overview
│
├── data/
│   ├── docs/                          # Input documents
│   ├── faiss_index/                   # Vector database
│   ├── logs/                          # System logs
│   └── search_results_*.txt           # Saved searches
│
├── src/
│   ├── main_enterprise.py             # Main entry point
│   │
│   ├── document_processing/           # Document loaders
│   │   ├── __init__.py
│   │   └── loaders.py                 # PDF, TXT, MD, JSON
│   │
│   ├── utils/                         # Utilities
│   │   ├── __init__.py
│   │   ├── logger.py                  # Logging
│   │   └── text_splitter.py           # Semantic chunking
│   │
│   └── vector_db/                     # Vector database
│       ├── __init__.py
│       ├── vector_store.py            # FAISS management
│       ├── ingestion_pipeline.py      # Document ingestion
│       └── search_engine.py           # Hybrid search
│
└── venv/                              # Virtual environment
```

## ✨ Key Features

### 🔍 **Advanced Search**
- **Hybrid Search**: Combines semantic (vector) + keyword (BM25) search
- **Semantic Search**: Understanding-based similarity
- **Keyword Search**: Exact term matching
- **Context Search**: Returns surrounding chunks for complete information

### 📄 **Document Processing**
- **Multi-format support**: PDF, TXT, MD, JSON
- **Metadata extraction**: Title, author, page numbers, timestamps
- **Smart chunking**: 1000 chars with 200 char overlap, paragraph-aware
- **Deduplication**: Content hash-based duplicate detection

### 💾 **Vector Store**
- **FAISS indexing**: Fast similarity search
- **Metadata tracking**: Full traceability per chunk
- **Version control**: Automatic update detection
- **Document management**: Add, update, remove documents

### 📊 **Enterprise Features**
- **Logging**: File + console with configurable levels
- **Statistics**: Document counts, chunk counts, ingestion history
- **Save results**: Export searches to files
- **Full text output**: No truncation, complete chunks
- **Agent-ready API**: Programmatic access for AI agents

### 🤖 **LLM-Powered Q&A** (NEW!)
- **AI-Generated Answers**: Gemini AI analyzes all retrieved chunks
- **Comprehensive Responses**: Synthesizes information from multiple sources
- **Source Citations**: LLM references specific chunks used
- **RAG Accuracy Showcase**: Validates retrieval quality automatically
- **Automatic Integration**: Works with all search modes (Hybrid, Semantic, Keyword, Context)
- **File Export**: Save AI-generated answers with timestamps

## 🎓 Usage Examples

### Search with Full Output
```
Enter command: H
Enter search query: network scanning configuration
Number of results: 10
Show full text? y
Save to file? y
```

### Context-Aware Search
```
Enter command: T
Enter search query: API authentication workflow
Number of results: 5
Context window: 2
Save to file? y
```

### Check System Status
```
Enter command: V

VECTOR STORE STATISTICS
Total Documents: 3
Total Chunks: 145
Total Vectors: 145
```

### LLM-Powered Q&A (NEW!)
```
Enter command: H
Enter search query: how to configure fingerprinting
Number of results: 5
Show full text? y
Save to file? y

[... Search results display ...]

======================================================================
  LLM-POWERED Q&A (Showcasing RAG Accuracy)
======================================================================

Analyzing retrieved chunks with Gemini AI...
Query: "how to configure fingerprinting"
Analyzing 5 retrieved chunks...

----------------------------------------------------------------------
LLM ANSWER:
----------------------------------------------------------------------
Based on the retrieved documentation, here's how to configure
fingerprinting in Pulse Policy Secure Profiler:

1. Navigate to Configuration Section
   Access Configuration > Network Discovery > Fingerprinting...

2. Enable Fingerprinting Module
   Toggle the fingerprinting feature...

[... Comprehensive AI-generated answer ...]

======================================================================
END OF LLM ANSWER
======================================================================

✓ LLM answer saved to: data/llm_answer_20251124_140530.txt
```

## 🤖 Agent Integration

### Python API

**Basic RAG Search:**
```python
from src.vector_db.search_engine import HybridSearchEngine

# Initialize
search = HybridSearchEngine()

# Search
results = search.search(
    query="how to configure profiler",
    k=10,
    search_mode='hybrid'
)

# Extract context
context = "\n\n".join([r.chunk_metadata.text for r in results])

# Pass to your LLM
prompt = f"Based on:\n{context}\n\nGenerate test cases..."
```

**RAG + LLM Q&A (NEW!):**
```python
from src.vector_db.search_engine import HybridSearchEngine
from src.utils.llm_qa import generate_qa_answer

# Initialize
search = HybridSearchEngine()

# Search
results = search.search("how to configure profiler", k=10)

# Extract chunks
chunks = [r.chunk_metadata.text for r in results]

# Get AI-generated answer
answer = generate_qa_answer("how to configure profiler", chunks)

# Use answer for test case generation or automation
print(answer)
```

### Integration Examples
- **CrewAI**: Custom tool with RAG search
- **LangChain**: Custom retriever
- **Direct API**: Import and use programmatically

## ⚙️ Configuration

Edit `config.py` to customize:

```python
# Chunking
CHUNK_SIZE = 1000              # Characters per chunk
CHUNK_OVERLAP = 200            # Overlap between chunks

# Search
DEFAULT_TOP_K = 5              # Default results count

# Embedding Model
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"  # Fast, accurate

# Logging
LOG_LEVEL = "INFO"             # DEBUG, INFO, WARNING, ERROR

# LLM Q&A (NEW!)
USE_LLM_QA = True              # Enable/disable LLM-powered Q&A
GEMINI_API_KEY = "your-key"    # Your Gemini API key
GEMINI_MODEL = "gemini-pro"    # Gemini model to use
LLM_TEMPERATURE = 0.3          # Lower = focused, higher = creative
LLM_MAX_TOKENS = 1024          # Maximum response length
```

## 📈 Performance Tips

### For Better Search Quality:
- Use **Hybrid Search [H]** for most queries
- Increase `k` to 10-20 for comprehensive coverage
- Use **Context Search [T]** for full sections
- Try different query phrasings

### For Faster Ingestion:
- Increase `EMBED_BATCH_SIZE` (32 → 64)
- Use smaller documents initially
- Monitor logs for errors

## 🐛 Troubleshooting

### No results found?
- Check [V] stats to verify docs are ingested
- Try [H] hybrid search instead of [S] semantic
- Increase number of results (k)

### Slow ingestion?
- Check `data/logs/rag_system.log`
- Reduce `EMBED_BATCH_SIZE` in config.py
- Verify PDF files are not corrupted

### Search results not relevant?
- Use more specific queries
- Try [K] keyword search for exact terms
- Check hybrid scores (should be >0.5)

## 📝 Documentation

- **[ENTERPRISE_RAG_DOCUMENTATION.txt](ENTERPRISE_RAG_DOCUMENTATION.txt)** - Complete guide (architecture, setup, usage)
- **[QUICK_START.txt](QUICK_START.txt)** - 5-minute quick reference
- **[SEARCH_OUTPUT_GUIDE.txt](SEARCH_OUTPUT_GUIDE.txt)** - Search features and output format
- **[SYSTEM_SUMMARY.txt](SYSTEM_SUMMARY.txt)** - Architecture and improvements overview

## 🔐 Security

- Add `data/` to `.gitignore` (contains sensitive documents)
- Never commit `data/faiss_index/` (contains embeddings)
- Use environment variables for sensitive config
- Restrict access to `data/` directory

## 📦 Dependencies

Core libraries:
- `faiss-cpu` - Vector similarity search
- `sentence-transformers` - Embeddings
- `torch` - Deep learning backend
- `pdfplumber` - PDF processing
- `scikit-learn` - ML utilities

See `requirements.txt` for complete list.

## 🎯 Use Cases

### Current:
- **Document Search**: Find relevant information in admin guides
- **API Discovery**: Locate API endpoints and workflows
- **Configuration Lookup**: Search for setup instructions

### Future (with Agent Integration):
- **Test Case Generation**: AI agents query docs to generate test cases
- **Automation Scripts**: Context for profiler automation
- **Knowledge Base**: Enterprise Q&A system

## 🚧 Roadmap

- [ ] Advanced chunking (table-aware, code-aware)
- [ ] Multi-modal support (images, diagrams)
- [ ] Query expansion (synonyms, acronyms)
- [ ] Re-ranking with cross-encoder
- [ ] REST API for remote access
- [ ] Web dashboard
- [ ] Distributed indexing for scale

## 📄 License

Internal use only - Ivanti Profiler Automation Team

## 📞 Support

For issues or questions:
- Check logs: `data/logs/rag_system.log`
- Review documentation in root directory
- Contact: Ivanti Profiler Automation Team

---

**Version**: 2.1 (Enterprise Edition + LLM Q&A)
**Last Updated**: 2025-11-24
**Status**: Production-Ready ✅
