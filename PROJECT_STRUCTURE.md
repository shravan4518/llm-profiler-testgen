# Project Structure - AI Test Case Generator

**Last Updated:** 2025-11-29
**Status:** Production-Ready

---

## 📁 **Root Directory Structure**

```
POC/
├── config.py                    # Central configuration file (Azure OpenAI, paths, settings)
├── requirements.txt             # Python dependencies
├── README.md                    # Main project documentation
├── PROJECT_STRUCTURE.md         # This file - project organization guide
│
├── run_testgen_simple.py        # ⭐ MAIN ENTRY POINT - Simplified test generator
├── run_testgen.py               # Multi-agent version (requires CrewAI)
│
├── venv_313/                    # Active Python virtual environment (Python 3.13)
│
├── src/                         # Source code (core system)
├── data/                        # Data storage (docs, indexes, outputs)
├── docs/                        # Documentation
└── scripts/                     # Utility scripts and tests
```

---

## 🎯 **Quick Start**

### **Generate Test Cases (Recommended)**

```bash
# 1. Activate virtual environment
venv_313\Scripts\activate

# 2. Run simplified test generator
python run_testgen_simple.py
```

### **Ingest Documents**

```bash
# Add documents to data/docs/ then run:
python src/main_enterprise.py
# Choose [I] Ingest documents
```

---

## 📂 **Detailed Directory Structure**

### **1. `/src` - Source Code**

```
src/
├── agents/                      # CrewAI agents (for multi-agent version)
│   ├── task_planner_agent.py
│   ├── test_generator_agent.py
│   └── validation_agent.py
│
├── document_processing/         # Document loaders and processing
│   ├── loaders.py               # PDF, TXT, DOCX loaders
│   └── image_processor.py       # Multimodal image processing
│
├── orchestration/               # Multi-agent orchestration
│   └── crew_orchestrator.py    # CrewAI workflow manager
│
├── utils/                       # Utility modules
│   ├── azure_llm.py             # Azure OpenAI integration
│   ├── logger.py                # Logging configuration
│   ├── output_formatter.py      # JSON/Markdown/Excel formatters
│   └── prompt_preprocessor.py   # Prompt analysis and optimization
│
├── vector_db/                   # Vector database and RAG
│   ├── vector_store.py          # FAISS vector store
│   ├── search_engine.py         # Hybrid search (semantic + BM25)
│   ├── enhanced_retrieval.py    # Multi-query adaptive retrieval
│   └── embedding_models.py      # Sentence-transformers models
│
├── main_enterprise.py           # RAG system (ingestion, search, Q&A)
├── simple_testgen.py            # ⭐ Simplified test case generator
└── testcase_generator.py        # Multi-agent test case generator
```

**Key Files:**
- **`simple_testgen.py`** - Fast, single-call test generation (recommended)
- **`testcase_generator.py`** - Multi-agent version (slower, more sophisticated)
- **`main_enterprise.py`** - Document ingestion and RAG Q&A
- **`azure_llm.py`** - Azure OpenAI wrapper
- **`output_formatter.py`** - Formats test cases to JSON/Markdown/Excel

---

### **2. `/data` - Data Storage**

```
data/
├── docs/                        # Source documents for ingestion
│   ├── .gitkeep
│   ├── PP-Profiler Design-241125-070351.pdf
│   └── ps-pps-9.1r10.0-profiler-administration-guide.pdf
│
├── faiss_index/                 # Vector database index
│   ├── faiss_index.bin          # FAISS index file
│   ├── chunk_metadata.pkl       # Chunk metadata
│   └── document_registry.pkl    # Document registry
│
├── test_cases/                  # Generated test cases
│   ├── test_cases_TIMESTAMP.json
│   ├── test_cases_TIMESTAMP.md
│   └── test_cases_TIMESTAMP.xlsx
│
├── logs/                        # System logs
│   └── rag_system.log
│
└── archive/                     # Old LLM outputs (archived)
    ├── llm_answer_*.txt
    └── search_results_*.txt
```

**Important:**
- Add your documentation files to `data/docs/`
- Generated test cases are in `data/test_cases/`
- FAISS index is in `data/faiss_index/` (auto-created on ingestion)

---

### **3. `/docs` - Documentation**

```
docs/
├── README_TESTGEN.md            # Test generation system overview
├── README_SIMPLE_VERSION.md     # Simplified version guide
├── QUICKSTART_SIMPLE.md         # Quick start guide
├── SETUP_AZURE_TESTGEN.md       # Multi-agent setup guide
├── AI_TESTGEN_IMPLEMENTATION_SUMMARY.md  # Implementation details
│
├── guides/                      # System guides
│   ├── ENTERPRISE_RAG_DOCUMENTATION.txt
│   └── SYSTEM_ARCHITECTURE.txt
│
└── archive/                     # Old/legacy documentation
    ├── CLEANUP_SUMMARY.txt
    ├── QUICK_START.txt
    ├── SEARCH_OUTPUT_GUIDE.txt
    ├── SYSTEM_SUMMARY.txt
    ├── GEMINI_FREE_TIER_FIX.txt
    ├── LLM_QA_FEATURE_GUIDE.txt
    ├── LLM_QA_TROUBLESHOOTING.txt
    ├── LLM_QA_UPDATE_SUMMARY.txt
    └── MULTIMODAL_SETUP_GUIDE.txt
```

**Key Documentation:**
- **Start here:** `docs/QUICKSTART_SIMPLE.md`
- **System overview:** `docs/README_SIMPLE_VERSION.md`
- **Architecture:** `docs/guides/SYSTEM_ARCHITECTURE.txt`

---

### **4. `/scripts` - Utility Scripts**

```
scripts/
├── tests/                       # Test and debug scripts
│   ├── test_generation.py       # Automated test generation
│   ├── test_parser.py           # Parser testing
│   ├── test_parser_debug.py     # Parser debugging
│   ├── test_regex.py            # Regex pattern testing
│   └── debug_output.py          # Debug LLM output
│
└── archive/                     # Old/archived scripts
    └── api-testing.py           # Legacy API testing
```

**Usage:**
- Test scripts are for development/debugging only
- Run from project root: `python scripts/tests/test_generation.py`

---

## 🔧 **Configuration**

### **Environment Variables (Recommended)**

```powershell
# Windows PowerShell
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
$env:AZURE_OPENAI_API_KEY = "your-api-key"
$env:AZURE_OPENAI_DEPLOYMENT = "gpt-4-1-nano"
```

### **OR Edit config.py Directly**

```python
# Lines 56-59 in config.py
AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
AZURE_OPENAI_API_KEY = "your-api-key"
AZURE_OPENAI_DEPLOYMENT = "gpt-4-1-nano"
AZURE_OPENAI_API_VERSION = "2024-08-01-preview"
```

---

## 📊 **Key Features**

### **1. Simplified Test Generator** (`run_testgen_simple.py`)
- ⚡ Fast: 10-15 seconds per feature
- 💰 Affordable: ~$0.001 per generation
- 📋 Comprehensive: 15-20 test cases per feature
- 📤 Multi-format: JSON, Markdown, Excel output

### **2. RAG System** (`src/main_enterprise.py`)
- 📚 Document ingestion (PDF, TXT, DOCX)
- 🔍 Hybrid search (semantic + keyword)
- 🤖 LLM-powered Q&A
- 📊 Statistics and monitoring

### **3. Multi-Agent Version** (`run_testgen.py`)
- 🤖 3 specialized agents (Planner, Generator, Validator)
- 🔄 CrewAI orchestration
- ⏱️ Slower (45-60 seconds) but more sophisticated
- 💸 More expensive (~$0.26 per feature)

---

## 🚀 **Common Workflows**

### **Workflow 1: Generate Test Cases**

```bash
# 1. Activate environment
venv_313\Scripts\activate

# 2. Ensure documents are ingested (one-time)
python src/main_enterprise.py
# Choose [I] Ingest documents

# 3. Generate test cases
python run_testgen_simple.py
# Enter feature description when prompted

# 4. Find outputs in data/test_cases/
```

### **Workflow 2: Search Documentation**

```bash
# 1. Activate environment
venv_313\Scripts\activate

# 2. Run RAG system
python src/main_enterprise.py

# 3. Choose [S] Search knowledge base
# Or [Q] Ask question (LLM-powered Q&A)
```

### **Workflow 3: Add New Documents**

```bash
# 1. Copy documents to data/docs/
copy your-new-doc.pdf data\docs\

# 2. Run ingestion
python src/main_enterprise.py
# Choose [I] Ingest documents

# 3. System indexes new documents automatically
```

---

## 📈 **Performance Metrics**

| Metric | Simplified | Multi-Agent |
|--------|------------|-------------|
| Speed | 10-15s | 45-60s |
| Cost/feature | ~$0.001 | ~$0.26 |
| Test cases | 15-20 | 15-20 |
| Quality | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Python version | Any | 3.10-3.13 |
| Dependencies | Minimal | CrewAI required |

---

## 🔍 **File Locations**

### **Input Files**
- Source documents: `data/docs/`
- Configuration: `config.py`

### **Output Files**
- Test cases: `data/test_cases/test_cases_TIMESTAMP.{json,md,xlsx}`
- Logs: `data/logs/rag_system.log`
- LLM answers: `data/llm_answer_TIMESTAMP.txt` (archived in `data/archive/`)

### **System Files**
- Vector index: `data/faiss_index/faiss_index.bin`
- Metadata: `data/faiss_index/chunk_metadata.pkl`
- Document registry: `data/faiss_index/document_registry.pkl`

---

## 🛠️ **Maintenance**

### **Clean Up Generated Files**

```bash
# Remove old test cases
del data\test_cases\*.json
del data\test_cases\*.md
del data\test_cases\*.xlsx

# Remove old LLM answers (already archived)
del data\archive\llm_answer_*.txt
```

### **Rebuild Vector Index**

```bash
# Delete existing index
del data\faiss_index\*.bin
del data\faiss_index\*.pkl

# Re-run ingestion
python src/main_enterprise.py
# Choose [I] Ingest documents
```

---

## 📝 **Notes**

- **Active Virtual Environment:** `venv_313` (Python 3.13)
- **Old venv removed:** The old `venv` folder has been deleted
- **Archive folders:** Old files are in `docs/archive/`, `data/archive/`, `scripts/archive/`
- **Test scripts:** Located in `scripts/tests/` for debugging purposes only

---

## ✅ **Project Status**

- ✅ Production-ready
- ✅ Fully documented
- ✅ Clean directory structure
- ✅ Working test generation (15 test cases per run)
- ✅ Cost-optimized (~$0.001 per generation)
- ✅ Multi-format output (JSON, Markdown, Excel)

---

**Last Cleanup:** 2025-11-29
**Maintained By:** Development Team
**Status:** Active Development / Production Use
