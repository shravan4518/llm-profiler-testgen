# Framework Code Ingestion Guide

## Overview

This guide explains how to ingest your **test automation framework code** into the vector database so the LLM can learn from it when generating test scripts.

---

## 🎯 Why Ingest Framework Code?

When generating test scripts from AI-generated test cases, the LLM needs to:
1. **Know your framework's APIs** (FWUtils, pcsAdmin, CommonUtils, etc.)
2. **Understand coding patterns** (error handling, logging, assertions)
3. **Learn naming conventions** (TC_XXX functions, test data structures)
4. **See example implementations** (complete test cases)

By ingesting your framework code into the RAG knowledge base, the LLM can **retrieve relevant code examples** and **generate scripts that match your framework's style**.

---

## 📁 Step-by-Step Instructions

### **Step 1: Organize Your Framework Code**

Place your framework in a directory, for example:

```
/path/to/framework/
├── FWUtils.py
├── CommonUtils.py
├── DesktopUtils.py
├── Initialize.py
├── admin/
│   ├── ProcsSA.py
│   └── ...
├── test_suites/
│   ├── Pulse_Desktop_Reference_TestSuite.py
│   ├── Pulse_Desktop_Reference_Data.py
│   └── ...
└── ...
```

### **Step 2: Run the Ingestion Script**

```bash
python ingest_framework.py --framework-path /path/to/your/framework
```

**Example:**
```bash
# If your framework is in C:\automation\pulse_framework
python ingest_framework.py --framework-path "C:\automation\pulse_framework"

# If your framework is in current directory
python ingest_framework.py --framework-path "."
```

### **Step 3: Verify Ingestion**

The script will show:
```
================================================================================
FRAMEWORK CODE INGESTION
================================================================================

[Step 1] Loading framework code from: C:\automation\pulse_framework
--------------------------------------------------------------------------------
✓ Loaded: FWUtils.py
✓ Loaded: CommonUtils.py
✓ Loaded: Pulse_Desktop_Reference_TestSuite.py
✓ Loaded: Pulse_Desktop_Reference_Data.py
...

✓ Loaded 15 framework files

[Step 2] Ingesting into vector database...
--------------------------------------------------------------------------------
✓ Ingested: FWUtils.py (12 chunks)
✓ Ingested: CommonUtils.py (8 chunks)
✓ Ingested: Pulse_Desktop_Reference_TestSuite.py (45 chunks)
...

================================================================================
INGESTION COMPLETE
================================================================================
Total files: 15
Successfully ingested: 15
Failed: 0
Total chunks added: 247

✓ Framework code is now searchable in the vector database!
✓ LLM can now learn from your framework patterns when generating test scripts
```

---

## 🔍 What Gets Ingested?

### **Automatically Detected Patterns:**

The ingestion script looks for these file patterns:
- `**/*TestSuite.py` - Test suite files
- `**/*_Data.py` - Test data files
- `**/FWUtils.py` - Framework utilities
- `**/CommonUtils.py` - Common utilities
- `**/DesktopUtils.py` - Desktop utilities
- `**/Initialize.py` - Initialization
- `**/admin/*.py` - Admin operations
- `**/*Utils.py` - Any utility files

### **Code Structure Extraction:**

For each Python file, the system extracts:
- **Imports** - Dependencies and modules
- **Classes** - Class names and methods
- **Functions** - Function names and signatures
- **Docstrings** - Function/class documentation

### **Enhanced for RAG:**

Each code file is enhanced with metadata:
```python
# ============================================================================
# FILE: FWUtils.py
# PATH: C:\automation\pulse_framework\FWUtils.py
# ============================================================================

# FRAMEWORK COMPONENT SUMMARY:
# This file is part of the Pulse Secure test automation framework.
#
# IMPORTS: logging, subprocess, json, ...
#
# CLASSES DEFINED: FWUtils
#
# FUNCTIONS DEFINED: request_desktop, get_logger, get_config, ...
#
# ============================================================================

# [Original code follows...]
```

This metadata helps the LLM understand what each file does and when to retrieve it.

---

## 🚀 How It Works During Script Generation

### **Before Framework Ingestion:**

LLM generates generic code:
```python
def test_export_db():
    # Generic, not using your framework
    selenium.get("https://pcs/admin")
    selenium.click("#export-button")
    assert file_exists("export.bin")
```

### **After Framework Ingestion:**

LLM retrieves relevant framework code and generates:
```python
def TC_001_PROFILER_01_EXPORT_DB():
    tc_id = sys._getframe().f_code.co_name
    log.info('-' * 50)
    log.info(tc_id + ' [START]')

    try:
        step_text = "Logging into PCS as admin"
        log.info(step_text)
        return_dict = pcsAdmin.loginSA()
        assert return_dict['status'] == 1, "Failed to login PCS as admin"

        step_text = "Exporting Profiler DB"
        log.info(step_text)
        export_params = {'format': 'binary', 'db_type': 'profiler_device'}
        return_dict = pcsAdmin.exportProfilerDB(export_params)
        assert return_dict['status'] == 1, "Failed to export Profiler DB"

        log.info(tc_id + ' [PASSED]')
        eresult = True

    except AssertionError as e:
        log.error(e)
        log.info(tc_id + ' [FAILED]')
        objCommonUtils.get_screenshot(file_name=tc_id)
        eresult = False

    log.info(tc_id + ' [END]')
    return eresult
```

**Notice:**
- ✅ Uses your framework's `pcsAdmin` module
- ✅ Follows your error handling pattern
- ✅ Uses your logging style
- ✅ Matches your function naming convention
- ✅ Includes screenshot on failure

---

## ⚙️ Advanced Usage

### **Ingest Specific Files Only:**

Edit `ingest_framework.py` to customize which files to include:

```python
documents = load_framework_repository(
    framework_path=framework_path,
    include_patterns=[
        '**/FWUtils.py',           # Only utilities
        '**/*TestSuite.py',        # Only test suites
        # Add more patterns as needed
    ]
)
```

### **Clear and Re-ingest:**

```bash
# Clear existing framework data and re-ingest
python ingest_framework.py --framework-path /path/to/framework --clear
```

### **Ingest Multiple Framework Versions:**

If you have different framework versions, ingest them all:
```bash
python ingest_framework.py --framework-path /path/to/framework_v1
python ingest_framework.py --framework-path /path/to/framework_v2
```

The LLM will learn patterns from all versions.

---

## 📊 Checking What's Ingested

### **Search for Framework Code:**

Use the main enterprise app to search:

```bash
python run_main_enterprise.py
```

Then search:
```
[S] Search (semantic)
Enter query: FWUtils request_desktop
```

You should see chunks from your framework code.

### **Verify in Vector Database:**

```python
from src.vector_db.search_engine import HybridSearchEngine

search = HybridSearchEngine()
results = search.search("request_desktop function", k=5)

for result in results:
    print(f"Source: {result.source}")
    print(f"Text: {result.text[:200]}...")
    print("-" * 80)
```

---

## 🎨 Test Script Generation Workflow

### **Complete Flow:**

```
1. User Prompt
   "Generate test cases for Profiler DB export"

2. AI Test Case Generation (Current System)
   ↓
   15-24 test cases in JSON

3. RAG Retrieval for Script Generation (NEW)
   ↓
   Query: "test suite function export database admin login"
   ↓
   Retrieved Chunks:
   - Pulse_Desktop_Reference_TestSuite.py (TC_567 function)
   - FWUtils.py (request_desktop API)
   - admin/ProcsSA.py (loginSA, exportProfilerDB)

4. LLM Script Generation
   ↓
   Executable Python scripts using your framework

5. Test Execution
   ↓
   pytest runs generated scripts
```

---

## 🔧 Troubleshooting

### **Issue: No files loaded**

**Check:**
1. Framework path is correct
2. Python files exist in the path
3. Files match the include patterns

**Fix:**
```bash
# List files that would be ingested
ls /path/to/framework/**/*TestSuite.py
ls /path/to/framework/**/*Utils.py
```

### **Issue: Import errors during ingestion**

**Cause:** Code file has syntax errors or missing dependencies

**Fix:** The system logs warnings but continues:
```
WARNING - Could not parse code structure for FWUtils.py: unexpected indent
```

Files with parse errors are still ingested (as plain text).

### **Issue: Framework code not being retrieved**

**Check:**
1. Code was successfully ingested (check logs)
2. Search query matches code content
3. Try searching for specific function names

**Test:**
```bash
python run_main_enterprise.py
# Search for a known function name
[S] Search
Enter query: loginSA
```

---

## 💡 Best Practices

### **1. Ingest Representative Examples**

Include:
- ✅ Complete test suites (with INITIALIZE, tests, CLEANUP)
- ✅ Test data files (to show data structure patterns)
- ✅ Utility modules (FWUtils, CommonUtils, etc.)
- ✅ Admin operations (pcsAdmin)

### **2. Keep Framework Updated**

Re-ingest when framework changes:
```bash
python ingest_framework.py --framework-path /path/to/framework
```

The system detects changes and updates only modified files.

### **3. Organize by Feature**

If you have many test suites, organize them:
```
framework/
├── core/          # Core utilities
├── vpn/           # VPN-related tests
├── profiler/      # Profiler-related tests
└── admin/         # Admin operations
```

Then ingest:
```bash
python ingest_framework.py --framework-path framework/core
python ingest_framework.py --framework-path framework/profiler
```

### **4. Document Your APIs**

Add docstrings to your framework functions:
```python
def request_desktop(operation: str, params: dict) -> dict:
    """
    Execute desktop automation operation

    Args:
        operation: Operation name (e.g., 'launch_pulse_app', 'connect_vpn')
        params: Operation parameters

    Returns:
        {'status': 1, ...} on success
        {'status': 0, 'error': '...'} on failure

    Example:
        request_desktop('connect_vpn', {'profile_name': 'vpn1', 'username': 'user'})
    """
```

The LLM will learn from these docstrings!

---

## 📈 Expected Results

### **Before Framework Ingestion:**
- LLM generates generic Python/pytest code
- May not match your framework's style
- Requires manual editing

### **After Framework Ingestion:**
- LLM generates code using your exact framework APIs
- Matches your coding patterns and conventions
- Minimal or no manual editing required
- ~80-90% of generated scripts work out-of-the-box

---

## 🎯 Next Steps

1. ✅ **Ingest your framework** using the script above
2. ✅ **Verify ingestion** by searching for framework code
3. ✅ **Build script generator** (next phase) that uses RAG to retrieve framework patterns
4. ✅ **Generate test scripts** from AI test cases
5. ✅ **Execute and iterate** on generated scripts

---

## Summary

**Command to run:**
```bash
python ingest_framework.py --framework-path /path/to/your/framework
```

**What it does:**
- Loads all Python files from your framework
- Extracts code structure (classes, functions, imports)
- Enhances with metadata for better RAG retrieval
- Ingests into vector database alongside documentation

**Result:**
- LLM can now retrieve relevant framework code when generating test scripts
- Generated scripts will match your framework's patterns and APIs
- Significantly reduces manual editing of generated code

Ready to ingest your framework? Run the command above with your framework path!
