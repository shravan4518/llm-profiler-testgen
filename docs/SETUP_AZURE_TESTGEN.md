# Azure OpenAI + CrewAI Test Case Generator - Setup Guide

## System Overview

This is an enterprise-grade AI-powered test case generation system that combines:

- **RAG (Retrieval-Augmented Generation)**: Retrieves relevant documentation context
- **Azure OpenAI GPT-4.1-nano**: Powers intelligent analysis and generation
- **CrewAI Multi-Agent Framework**: Coordinates specialized AI agents for maximum test coverage
- **Multi-format Output**: JSON, Markdown, and Excel exports

## Architecture

```
User Prompt → Prompt Preprocessor → RAG Retrieval → Context Enrichment →
CrewAI Orchestration (3 Agents) → Test Cases → Multi-format Export
```

### AI Agents

1. **Task Planner Agent**: Analyzes feature requirements and plans comprehensive test coverage
2. **Test Generator Agent**: Generates detailed, executable test cases
3. **Validation Agent**: Validates test quality, coverage, and completeness

## Prerequisites

- Python 3.10-3.13 (CrewAI requires this range)
- Azure OpenAI account with GPT-4 access
- Documents ingested into RAG system

## Installation

### Step 1: Install Dependencies

Due to Python 3.14 compatibility issues with CrewAI, you have two options:

#### Option A: Use Python 3.13 or earlier (Recommended)

```bash
# Create new virtual environment with Python 3.13
python3.13 -m venv venv
venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt
```

#### Option B: Manual Package Installation

If CrewAI installation fails, use this alternative approach:

```bash
# Install core dependencies first
pip install openai==1.109.0
pip install langchain==0.1.20 langchain-core==1.1.0
pip install openpyxl tabulate

# Note: CrewAI orchestration requires Python 3.10-3.13
# For Python 3.14, you can still use the system with direct agent implementation
```

### Step 2: Configure Azure OpenAI

Set environment variables (or update config.py):

**Windows:**
```bash
set AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
set AZURE_OPENAI_API_KEY=your-api-key-here
set AZURE_OPENAI_DEPLOYMENT=gpt-4-1-nano
```

**Linux/Mac:**
```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-api-key-here"
export AZURE_OPENAI_DEPLOYMENT="gpt-4-1-nano"
```

Or edit `config.py` directly:

```python
# Azure OpenAI Configuration (Production LLM)
AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
AZURE_OPENAI_API_KEY = "your-api-key-here"
AZURE_OPENAI_DEPLOYMENT = "gpt-4-1-nano"
```

### Step 3: Ingest Documents

Before generating test cases, ingest your documentation:

```bash
cd "c:\Users\SaiShravan.V\OneDrive - Ivanti\Desktop\POC"

# Copy your documentation to data/docs/
# Then run ingestion
venv\Scripts\python.exe src\main_enterprise.py

# Choose [I] to ingest documents
```

## Usage

### Method 1: Interactive Mode

```bash
venv\Scripts\python.exe src\testcase_generator.py
```

This will:
1. Prompt you for a feature description
2. Retrieve relevant documentation from RAG
3. Execute multi-agent workflow
4. Generate comprehensive test cases
5. Export to JSON, Markdown, and Excel

### Method 2: Programmatic Use

```python
from src.testcase_generator import TestCaseGenerator

# Initialize generator
generator = TestCaseGenerator()

# Generate test cases
result = generator.generate(
    user_prompt="Test case generation for user authentication feature",
    output_formats=['json', 'markdown', 'excel'],
    use_iteration=True  # Enable iterative refinement
)

# Access results
print(f"Status: {result['status']}")
print(f"Test Plan: {result['test_plan']}")
print(f"Test Cases: {result['test_cases']}")
print(f"Validation: {result['validation_report']}")
print(f"Files: {result['output_files']}")
```

### Method 3: API Integration

```python
from src.orchestration.crew_orchestrator import CrewOrchestrator
from src.utils.prompt_preprocessor import PromptPreprocessor
from src.vector_db.enhanced_retrieval import EnhancedRetrieval

# Setup components
preprocessor = PromptPreprocessor()
retrieval = EnhancedRetrieval(search_engine)
orchestrator = CrewOrchestrator()

# Process user input
analysis = preprocessor.analyze_prompt(user_input)
rag_results = retrieval.adaptive_retrieve(analysis['search_queries'])
enriched_context = preprocessor.enrich_context(user_input, rag_results)

# Generate test cases
result = orchestrator.generate_test_cases(enriched_context)
```

## Output Formats

### JSON Output
```json
{
  "generated_at": "2025-11-29T12:00:00",
  "total_test_cases": 15,
  "test_cases": [
    {
      "test_id": "TC_001",
      "title": "Verify successful user login",
      "category": "positive",
      "priority": "Critical",
      "description": "...",
      "prerequisites": "...",
      "test_data": "...",
      "test_steps": [...],
      "expected_results": "...",
      "postconditions": "..."
    }
  ]
}
```

### Markdown Output
- Formatted test case report
- Easy to review and share
- Can be imported into test management tools

### Excel Output
- Spreadsheet with all test cases
- Columns: Test ID, Title, Category, Priority, Description, etc.
- Ready for import into Jira, TestRail, etc.

## Configuration

### Test Generation Settings (config.py)

```python
# LLM Configuration
LLM_TEMPERATURE = 0.7  # Creativity level (0-1)
LLM_MAX_TOKENS = 4096  # Maximum response length

# Agent Configuration
ENABLE_CREWAI = True  # Enable multi-agent orchestration
MAX_ITERATIONS = 3  # Iterative refinement cycles

# Test Case Requirements
MIN_TEST_CASES_PER_FEATURE = 10  # Minimum test cases
COVERAGE_TYPES = [
    "positive",      # Happy path scenarios
    "negative",      # Error handling
    "boundary",      # Edge cases
    "integration",   # Component interactions
    "security",      # Security testing
    "performance"    # Performance testing
]

# Output Formats
OUTPUT_FORMATS = ["json", "markdown", "excel"]
```

## System Components

### New Files Created

1. **src/utils/azure_llm.py** - Azure OpenAI integration
2. **src/utils/prompt_preprocessor.py** - Prompt analysis and enrichment
3. **src/vector_db/enhanced_retrieval.py** - Multi-query RAG optimization
4. **src/agents/task_planner_agent.py** - Planning agent
5. **src/agents/test_generator_agent.py** - Generation agent
6. **src/agents/validation_agent.py** - Validation agent
7. **src/orchestration/crew_orchestrator.py** - Multi-agent workflow
8. **src/utils/output_formatter.py** - Multi-format export
9. **src/testcase_generator.py** - Main workflow pipeline

### Modified Files

1. **config.py** - Added Azure OpenAI and CrewAI configuration
2. **requirements.txt** - Added new dependencies

## Troubleshooting

### CrewAI Installation Fails

**Issue**: Python 3.14 is too new for CrewAI
**Solution**: Use Python 3.10-3.13, or use alternative implementation without CrewAI

### Azure OpenAI Authentication Error

**Issue**: Invalid credentials
**Solution**: Verify environment variables or config.py settings

### No Documents in Knowledge Base

**Issue**: RAG returns no results
**Solution**: Run document ingestion first: `[I] Ingest documents`

### Low Quality Test Cases

**Issue**: Generated test cases lack detail
**Solution**: Use `use_iteration=True` for iterative refinement

## Cost Estimation

### Azure OpenAI Pricing (example rates)

- GPT-4 Input: ~$0.03 per 1K tokens
- GPT-4 Output: ~$0.06 per 1K tokens

### Typical Test Generation Cost

For a medium feature (1,000 token input, 3,000 token output):

- Input: 1,000 tokens × $0.03 / 1,000 = $0.03
- Output: 3,000 tokens × $0.06 / 1,000 = $0.18
- **Total per feature: ~$0.21**

For 100 features: ~$21

## Advanced Features

### Iterative Refinement

Enable iterative improvement for higher quality:

```python
result = generator.generate(
    user_prompt="...",
    use_iteration=True  # Enables up to 3 refinement cycles
)
```

### Custom Coverage Types

Modify `config.py` to add custom coverage types:

```python
COVERAGE_TYPES = [
    "positive", "negative", "boundary",
    "accessibility",  # Custom
    "localization",   # Custom
    "compliance"      # Custom
]
```

### Multi-Query Optimization

The RAG system automatically:
- Generates multiple search queries from user input
- Retrieves results from multiple perspectives
- Deduplicates and ranks by relevance
- Expands context with neighboring chunks

## Best Practices

1. **Clear Feature Descriptions**: Provide detailed, specific feature descriptions
2. **Ingest Comprehensive Docs**: More documentation = better test coverage
3. **Review Generated Tests**: Always review and refine generated test cases
4. **Use Iteration**: Enable iterative refinement for critical features
5. **Export Multiple Formats**: Use JSON for automation, Excel for manual review

## Support

For issues or questions:
1. Check logs in `data/logs/rag_system.log`
2. Review generated output files
3. Verify Azure OpenAI configuration
4. Ensure documents are properly ingested

## Next Steps

1. Configure Azure OpenAI credentials
2. Ingest your documentation
3. Run test generation for a sample feature
4. Review and refine the output
5. Integrate into your CI/CD pipeline

---

**System Version**: 3.0 (Azure OpenAI + CrewAI Multi-Agent)
**Last Updated**: 2025-11-29
