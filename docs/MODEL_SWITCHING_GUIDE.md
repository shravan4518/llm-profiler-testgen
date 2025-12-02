# Model Switching Guide - Azure OpenAI

**Last Updated:** 2025-11-29

---

## 🎯 **Quick Model Switch**

To switch between GPT models, simply edit **ONE line** in `config.py`:

```python
# Line 71 in config.py
AZURE_OPENAI_DEPLOYMENT = "gpt-5.1-2"  # <-- Change model name here
```

**That's it!** The system automatically handles compatibility.

---

## 📋 **Supported Models**

| Model Name | Description | Speed | Cost | Token Parameter |
|------------|-------------|-------|------|-----------------|
| `gpt-4-1-nano` | GPT-4.1 Nano (fast, cheap) | ⚡⚡⚡ | 💰 | `max_tokens` |
| `gpt-4o` | GPT-4 Optimized | ⚡⚡ | 💰💰 | `max_tokens` |
| `gpt-5.1-2` | GPT-5.1 (latest) | ⚡ | 💰💰💰 | `max_completion_tokens` |
| `gpt-5-preview` | GPT-5 Preview | ⚡ | 💰💰💰 | `max_completion_tokens` |

---

## 🔄 **How It Works**

### **Automatic Parameter Handling**

The system automatically detects which parameter format to use:

**Old Models (GPT-4, GPT-4.1):**
```python
response = client.chat.completions.create(
    max_tokens=8000  # ✅ Works
)
```

**New Models (GPT-5+):**
```python
response = client.chat.completions.create(
    max_completion_tokens=8000  # ✅ Works
)
```

**Your Code (automatic):**
```python
# You just call:
llm.generate(prompt="...", max_tokens=8000)

# System handles the rest automatically!
# - Tries max_completion_tokens first (GPT-5+)
# - Falls back to max_tokens if needed (GPT-4)
```

---

## 🛠️ **Step-by-Step Model Switching**

### **Option 1: Edit config.py (Recommended)**

1. Open `config.py`
2. Find line 71:
   ```python
   AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.1-2")
   ```
3. Change the model name:
   ```python
   AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4-1-nano")
   ```
4. Save and run:
   ```bash
   python run_testgen_simple.py
   ```

### **Option 2: Environment Variable**

Set environment variable (temporary, doesn't modify files):

**Windows PowerShell:**
```powershell
$env:AZURE_OPENAI_DEPLOYMENT = "gpt-4-1-nano"
python run_testgen_simple.py
```

**Windows CMD:**
```cmd
set AZURE_OPENAI_DEPLOYMENT=gpt-4-1-nano
python run_testgen_simple.py
```

**Linux/Mac:**
```bash
export AZURE_OPENAI_DEPLOYMENT="gpt-4-1-nano"
python run_testgen_simple.py
```

---

## 📊 **Model Comparison**

### **GPT-4.1 Nano (Recommended for Cost)**

```python
AZURE_OPENAI_DEPLOYMENT = "gpt-4-1-nano"
```

**Pros:**
- ✅ Fastest (10-15 seconds)
- ✅ Cheapest (~$0.001 per generation)
- ✅ Perfect for test case generation
- ✅ High quality output

**Cons:**
- ⚠️ Smaller context window than GPT-5

**Use Case:** Production test case generation, high-volume usage

---

### **GPT-5.1 (Recommended for Quality)**

```python
AZURE_OPENAI_DEPLOYMENT = "gpt-5.1-2"
```

**Pros:**
- ✅ Latest model
- ✅ Best reasoning capabilities
- ✅ Larger context window
- ✅ Better at complex requirements

**Cons:**
- ⚠️ Slower (15-25 seconds)
- ⚠️ More expensive (~$0.003-0.005 per generation)

**Use Case:** Complex features, critical test cases, maximum quality needed

---

### **GPT-4o (Balanced)**

```python
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
```

**Pros:**
- ✅ Balanced speed/cost
- ✅ Good quality
- ✅ Multimodal capabilities

**Cons:**
- ⚠️ Mid-tier pricing

**Use Case:** General purpose, balanced requirements

---

## 💰 **Cost Comparison**

| Model | Cost per 1K Test Cases | Cost per 10K Test Cases |
|-------|------------------------|-------------------------|
| GPT-4.1 Nano | ~$1 | ~$10 |
| GPT-4o | ~$2 | ~$20 |
| GPT-5.1 | ~$3-5 | ~$30-50 |

---

## 🔍 **Verify Current Model**

Run this to see which model you're using:

```bash
python -c "import config; print(f'Current model: {config.AZURE_OPENAI_DEPLOYMENT}')"
```

Or check at runtime:
```bash
python run_testgen_simple.py
# Look for: "Azure OpenAI initialized: gpt-5.1-2"
```

---

## 🎨 **RAG + LLM Knowledge Mixing**

The system is configured to use **BOTH** RAG context and the model's general knowledge:

### **Prompt Structure:**

```
Generate test cases using BOTH:
1. Documentation context (from RAG retrieval)
2. Your general testing knowledge

Instructions:
- Use documentation as PRIMARY source for product-specific details
- Apply general testing knowledge for comprehensive coverage
- Combine both sources for realistic, executable test cases
```

### **How It Works:**

**Example: "Profiler DB upgrade"**

**RAG Context (from docs):**
- Profiler specific upgrade procedures
- Database schema details
- Version compatibility info

**LLM Knowledge (built-in):**
- Database upgrade best practices
- Rollback scenarios
- Backup verification tests
- Concurrent access testing
- Performance degradation checks

**Result:** Comprehensive test cases covering both product-specific requirements AND general database upgrade best practices!

---

## 🚀 **Best Practices**

### **For Production (High Volume)**

```python
AZURE_OPENAI_DEPLOYMENT = "gpt-4-1-nano"  # Cost-effective
LLM_MAX_TOKENS = 6000  # Sufficient for 15 test cases
```

### **For Critical Features**

```python
AZURE_OPENAI_DEPLOYMENT = "gpt-5.1-2"  # Best quality
LLM_MAX_TOKENS = 8000  # Maximum detail
```

### **For Experimentation**

```python
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"  # Balanced
LLM_MAX_TOKENS = 6000  # Standard
```

---

## 🐛 **Troubleshooting**

### **Error: "Unsupported parameter: max_tokens"**

**Cause:** Trying to use GPT-5+ with old parameter format

**Solution:** Already fixed! The system now auto-detects and uses the correct parameter.

**Verification:**
```bash
# This should work with ANY model now:
python run_testgen_simple.py
```

### **Error: "Model deployment not found"**

**Cause:** Model name doesn't match your Azure deployment

**Solution:**
1. Check your Azure Foundry deployments
2. Use the exact deployment name from Azure
3. Update `config.py` with the correct name

### **Slow Generation**

**Cause:** Using a more powerful model (GPT-5)

**Solution:**
- Switch to `gpt-4-1-nano` for speed
- Or reduce `LLM_MAX_TOKENS` for faster generation

---

## 📝 **Configuration Summary**

```python
# config.py - Lines 55-77

# Model Selection (change here)
AZURE_OPENAI_DEPLOYMENT = "gpt-5.1-2"  # <-- Your model

# Generation Parameters
LLM_TEMPERATURE = 0.7   # Creativity (0.0-1.0)
LLM_MAX_TOKENS = 8000   # Output length
LLM_TOP_P = 0.9         # Sampling quality
```

---

## ✅ **Testing Model Switch**

After changing the model, verify it works:

```bash
# 1. Activate environment
venv_313\Scripts\activate

# 2. Run test generation
python run_testgen_simple.py

# 3. Check logs for model name
# Should see: "Azure OpenAI initialized: <your-model>"

# 4. Verify output quality
# Check data/test_cases/ for generated files
```

---

## 🎯 **Recommendations**

| Use Case | Recommended Model | Why |
|----------|------------------|-----|
| **Daily testing** | `gpt-4-1-nano` | Fast, cheap, great quality |
| **Critical features** | `gpt-5.1-2` | Maximum quality and reasoning |
| **Balanced** | `gpt-4o` | Good middle ground |
| **Experimentation** | `gpt-4-1-nano` | Low cost for testing |
| **High volume** | `gpt-4-1-nano` | Best cost efficiency |

---

## 🚨 **Important Notes**

1. ✅ **No code changes needed** - Just edit config.py
2. ✅ **Automatic parameter handling** - Works with all models
3. ✅ **RAG + LLM knowledge** - Always uses both sources
4. ✅ **Backward compatible** - Switch back anytime
5. ✅ **No retraining needed** - Instant model switching

---

**Current Model:** Check `config.py` line 71

**Last Tested:** 2025-11-29

**Status:** ✅ Fully Working - Supports GPT-4, GPT-4.1, GPT-5, and future models
