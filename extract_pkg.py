"""
PKG Extractor: Extract Product Knowledge Graph from PDF documentation
Uses LLM to extract structured PKG data following the staged approach
"""

import json
import os
from pathlib import Path
import PyPDF2
from openai import AzureOpenAI
from dotenv import load_dotenv

# Load environment
load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-05-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

def extract_pdf_pages(pdf_path: str, start_page: int, end_page: int) -> str:
    """Extract text from PDF pages"""
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)

        text_parts = []
        for page_num in range(start_page - 1, min(end_page, len(pdf_reader.pages))):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            text_parts.append(f"[PAGE {page_num + 1}]\n{text}")

        return "\n\n".join(text_parts)

def extract_feature_understanding(pdf_content: str) -> dict:
    """STAGE 1: Extract Feature Understanding Layer"""

    prompt = f"""Analyze the following product documentation and extract the Feature Understanding Layer.

DOCUMENTATION:
{pdf_content}

YOUR TASK:
Extract a structured feature descriptor that normalizes the feature names and anchors them to product reality.

Return ONLY valid JSON in this format:
{{
  "features": [
    {{
      "feature_id": "unique_snake_case_id",
      "feature_name": "Human Readable Name",
      "domain": "Product Domain (e.g., Profiler)",
      "feature_type": "configuration_screen | workflow | report | etc",
      "confidence": "high | medium | low",
      "documentation_references": [
        "Page X: Section Title"
      ],
      "parent_feature": "parent_feature_id if this is a sub-feature",
      "description": "Brief description of what this feature does"
    }}
  ]
}}

RULES:
1. Extract ALL distinct features/screens mentioned in the documentation
2. Use snake_case for feature_id (e.g., "basic_profiler_config")
3. Identify parent-child relationships (Basic Config vs Advanced Config)
4. Include page references
5. Be comprehensive - extract EVERY feature mentioned

Return ONLY the JSON, no other text."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a technical documentation analyst. Extract structured feature information. Return ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_completion_tokens=8000
    )

    result_text = response.choices[0].message.content

    # Extract JSON
    if '```json' in result_text:
        result_text = result_text.split('```json')[1].split('```')[0].strip()
    elif '```' in result_text:
        result_text = result_text.split('```')[1].split('```')[0].strip()

    return json.loads(result_text)

def extract_pkg_for_feature(pdf_content: str, feature_name: str) -> dict:
    """STAGE 2: Extract Product Knowledge Graph (PKG) for a specific feature"""

    prompt = f"""Extract comprehensive Product Knowledge Graph (PKG) for the feature: "{feature_name}"

DOCUMENTATION:
{pdf_content}

YOUR TASK:
Extract COMPLETE PKG structure with ALL product details for this feature.

Return ONLY valid JSON in this EXACT format:
{{
  "feature_id": "snake_case_id",
  "feature_name": "{feature_name}",

  "ui_surfaces": [
    {{
      "screen_id": "unique_screen_id",
      "screen_name": "Screen Title as shown in UI",
      "navigation_path": "Menu -> Submenu -> Screen",
      "url_pattern": "/path/to/screen (if mentioned)",
      "requires_role": ["role1", "role2"],
      "page_reference": "Page X"
    }}
  ],

  "inputs": [
    {{
      "input_id": "unique_input_id",
      "name": "Field Label",
      "control_type": "textbox | checkbox | dropdown | radio | button | upload",
      "data_type": "string | integer | boolean | file",
      "range": "min-max (if applicable)",
      "default_value": "default value",
      "unit": "unit if applicable (minutes, percentage, etc)",
      "validation": "validation rule",
      "required": true/false,
      "visible_when": "condition for visibility",
      "help_text": "help text or description",
      "location": "section name where this appears",
      "page_reference": "Page X"
    }}
  ],

  "actions": [
    {{
      "action_id": "action_id",
      "button_text": "Button Text",
      "type": "submit | reset | delete | custom",
      "enabled_when": "condition",
      "description": "what this action does",
      "page_reference": "Page X"
    }}
  ],

  "constraints": [
    "Constraint 1 from documentation",
    "Constraint 2...",
    "Prerequisites and dependencies"
  ],

  "errors": [
    {{
      "error_id": "ERR_CODE",
      "message": "Exact error message from documentation",
      "trigger": "what causes this error",
      "page_reference": "Page X"
    }}
  ],

  "states": ["state1", "state2", "state3"],

  "state_transitions": [
    {{
      "from": "state1",
      "to": "state2",
      "trigger": "user action or condition"
    }}
  ],

  "workflows": [
    {{
      "workflow_id": "workflow_id",
      "name": "Workflow Name",
      "steps": ["Step 1", "Step 2", "Step 3"],
      "prerequisites": ["Prerequisite 1"],
      "page_reference": "Page X"
    }}
  ]
}}

CRITICAL RULES:
1. Extract EVERY input field/control mentioned for this feature
2. Include EXACT field names, labels, and default values from documentation
3. Capture ALL validation rules, ranges, and constraints
4. Extract ANY error messages mentioned
5. Include page references for traceability
6. Be COMPREHENSIVE - missing details = generic tests later
7. If a detail is not mentioned, omit that field (don't invent)
8. For checkboxes, note what they enable/disable
9. Capture section names where fields appear
10. Extract any configuration dependencies

Return ONLY the JSON, no other text."""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a software product analyst. Extract complete, accurate PKG data from documentation. Return ONLY valid JSON. Never invent details not in the documentation."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
        max_completion_tokens=16000
    )

    result_text = response.choices[0].message.content

    # Extract JSON
    if '```json' in result_text:
        result_text = result_text.split('```json')[1].split('```')[0].strip()
    elif '```' in result_text:
        result_text = result_text.split('```')[1].split('```')[0].strip()

    return json.loads(result_text)

def main():
    print("=" * 80)
    print("PKG EXTRACTOR: Product Knowledge Graph from Documentation")
    print("=" * 80)

    # Configuration
    pdf_path = r"c:\Users\SaiShravan.V\OneDrive - Ivanti\Desktop\POC\data\docs\ps-pps-9.1r10.0-profiler-administration-guide.pdf"
    start_page = 1
    end_page = 58
    output_dir = Path(r"c:\Users\SaiShravan.V\OneDrive - Ivanti\Desktop\POC\data\pkg")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Extract PDF content
    print(f"\n[STEP 1] Extracting PDF pages {start_page}-{end_page}...")
    pdf_content = extract_pdf_pages(pdf_path, start_page, end_page)
    print(f"[OK] Extracted {len(pdf_content)} characters")

    # Step 2: Extract Feature Understanding Layer
    print(f"\n[STEP 2] Extracting Feature Understanding Layer...")
    features = extract_feature_understanding(pdf_content)

    feature_understanding_file = output_dir / "feature_understanding.json"
    with open(feature_understanding_file, 'w', encoding='utf-8') as f:
        json.dump(features, f, indent=2, ensure_ascii=False)

    print(f"[OK] Identified {len(features.get('features', []))} features")
    for feat in features.get('features', []):
        print(f"  - {feat['feature_name']} ({feat['feature_id']})")

    # Step 3: Extract PKG for each feature
    print(f"\n[STEP 3] Extracting PKG for each feature...")

    for feature in features.get('features', []):
        feature_name = feature['feature_name']
        feature_id = feature['feature_id']

        print(f"\n  -> Extracting PKG for: {feature_name}")

        pkg = extract_pkg_for_feature(pdf_content, feature_name)

        # Save PKG
        pkg_file = output_dir / f"pkg_{feature_id}.json"
        with open(pkg_file, 'w', encoding='utf-8') as f:
            json.dump(pkg, f, indent=2, ensure_ascii=False)

        print(f"    [OK] Extracted:")
        print(f"      - {len(pkg.get('ui_surfaces', []))} UI surfaces")
        print(f"      - {len(pkg.get('inputs', []))} input controls")
        print(f"      - {len(pkg.get('actions', []))} actions")
        print(f"      - {len(pkg.get('constraints', []))} constraints")
        print(f"      - {len(pkg.get('errors', []))} error conditions")

    print(f"\n{'='*80}")
    print(f"[OK] PKG EXTRACTION COMPLETE")
    print(f"  Output directory: {output_dir}")
    print(f"  Files created:")
    print(f"    - feature_understanding.json")
    for feature in features.get('features', []):
        print(f"    - pkg_{feature['feature_id']}.json")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
