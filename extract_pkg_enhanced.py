"""
ENHANCED PKG Extractor: Handles scattered features and image analysis
Improvements:
1. Two-phase extraction: Discover feature locations globally, then extract from ALL pages
2. GPT-4o Vision for UI screenshots and diagrams
3. Topic consolidation for scattered features (e.g., DDR across multiple pages)
"""

import json
import os
import base64
from pathlib import Path
from typing import Dict, List, Tuple
import PyPDF2
from PIL import Image
import io
from openai import AzureOpenAI
from dotenv import load_dotenv

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


def extract_images_from_pdf(pdf_path: str, page_numbers: List[int]) -> List[Dict]:
    """
    Extract images from specific PDF pages and analyze with Vision model
    """
    images_analyzed = []

    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)

        for page_num in page_numbers:
            if page_num < 1 or page_num > len(pdf_reader.pages):
                continue

            page = pdf_reader.pages[page_num - 1]

            # Check for images on page
            if '/XObject' not in page['/Resources']:
                continue

            xobject = page['/Resources']['/XObject'].get_object()

            for obj_name in xobject:
                obj = xobject[obj_name]

                if obj['/Subtype'] == '/Image':
                    try:
                        # Extract image data
                        size = (obj['/Width'], obj['/Height'])
                        data = obj.get_data()

                        # Convert to PIL Image
                        if obj['/ColorSpace'] == '/DeviceRGB':
                            mode = "RGB"
                        else:
                            mode = "P"

                        img = Image.frombytes(mode, size, data)

                        # Convert to base64 for Vision API
                        buffered = io.BytesIO()
                        img.save(buffered, format="PNG")
                        img_base64 = base64.b64encode(buffered.getvalue()).decode()

                        # Analyze with GPT-4o Vision
                        analysis = analyze_image_with_vision(img_base64, page_num)

                        images_analyzed.append({
                            'page': page_num,
                            'analysis': analysis,
                            'image_type': analysis.get('type', 'unknown')
                        })

                        print(f"      [IMAGE] Page {page_num}: {analysis.get('type', 'unknown')} - {analysis.get('summary', '')[:80]}...")

                    except Exception as e:
                        print(f"      [WARNING] Could not analyze image on page {page_num}: {e}")

    return images_analyzed


def analyze_image_with_vision(image_base64: str, page_num: int) -> Dict:
    """
    Analyze image using GPT-4o Vision model
    Identifies: UI screenshots, workflow diagrams, architecture diagrams, configuration screens
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing technical documentation images. Identify the image type and extract key information."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Analyze this image from technical documentation and return JSON:

{
  "type": "ui_screenshot | workflow_diagram | architecture_diagram | configuration_screen | table | other",
  "summary": "Brief description of what this shows",
  "ui_elements": ["list of UI elements if screenshot (buttons, fields, menus)"],
  "workflow_steps": ["list of steps if workflow diagram"],
  "components": ["list of components if architecture"],
  "field_names": ["list of field names if configuration screen"],
  "relationships": ["relationships shown in diagram"],
  "key_information": ["any other key details visible"]
}

Return ONLY valid JSON."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=1000
        )

        result_text = response.choices[0].message.content

        # Extract JSON
        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0].strip()
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0].strip()

        return json.loads(result_text)

    except Exception as e:
        print(f"      [ERROR] Vision analysis failed: {e}")
        return {
            "type": "unknown",
            "summary": "Analysis failed",
            "error": str(e)
        }


def discover_features_with_page_locations(pdf_content: str) -> Dict:
    """
    PHASE 1: Global feature discovery - Find ALL pages where each feature is mentioned

    This solves the scattered feature problem:
    - DDR on pages 5, 12, 30, 45 → Returns {"DDR": [5, 12, 30, 45]}
    """

    prompt = f"""Analyze this COMPLETE documentation and identify ALL features/topics mentioned.

For EACH feature, list ALL page numbers where it's mentioned (even briefly).

CRITICAL for scattered features:
- If "DDR" or "Device Discovery" appears on multiple pages, create ONE unified feature with ALL page numbers
- If "Profile Groups" is mentioned on pages 12, 30, 45, list all three pages
- Consolidate variations (e.g., "WMI Config", "WMI Profiling", "WMI Settings" → one feature)

DOCUMENTATION (showing first 80,000 chars, full document is {len(pdf_content)} chars):
{pdf_content[:80000]}

Return JSON:
{{
  "features": [
    {{
      "feature_name": "Device Discovery and Registration (DDR)",
      "alternative_names": ["DDR", "Device Discovery", "Discovery and Registration"],
      "page_locations": [5, 12, 18, 30, 45],
      "feature_type": "workflow | configuration_screen | report",
      "key_sections": ["Overview on page 5", "Configuration on page 12", "Integration on page 30"]
    }}
  ]
}}

IMPORTANT:
- Identify 15-25 major features
- Include ALL pages where feature is mentioned
- Consolidate related terms into one feature
- Mark features scattered across >3 pages

Return ONLY valid JSON."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a documentation analyzer. Identify features and ALL their page locations. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_completion_tokens=8000
        )

        result_text = response.choices[0].message.content

        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0].strip()
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0].strip()

        return json.loads(result_text)

    except Exception as e:
        print(f"[ERROR] Feature discovery failed: {e}")
        return {"features": []}


def extract_pkg_from_scattered_pages(pdf_path: str, feature_name: str, page_numbers: List[int], images: List[Dict]) -> Dict:
    """
    PHASE 2: Extract PKG from ALL pages where feature is mentioned + image analysis
    """

    # Extract content from ALL relevant pages
    relevant_content_parts = []

    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)

        for page_num in page_numbers:
            if page_num < 1 or page_num > len(pdf_reader.pages):
                continue
            page = pdf_reader.pages[page_num - 1]
            text = page.extract_text()
            relevant_content_parts.append(f"[PAGE {page_num}]\n{text}")

    combined_content = "\n\n".join(relevant_content_parts)

    # Filter images for this feature's pages
    feature_images = [img for img in images if img['page'] in page_numbers]

    # Build image context
    image_context = ""
    if feature_images:
        image_context = "\n\n=== IMAGE ANALYSIS ===\n"
        for img in feature_images:
            image_context += f"\nPage {img['page']} - {img['analysis'].get('type', 'unknown')}:\n"
            image_context += f"  Summary: {img['analysis'].get('summary', 'N/A')}\n"

            if img['analysis'].get('ui_elements'):
                image_context += f"  UI Elements: {', '.join(img['analysis']['ui_elements'])}\n"
            if img['analysis'].get('field_names'):
                image_context += f"  Fields: {', '.join(img['analysis']['field_names'])}\n"
            if img['analysis'].get('workflow_steps'):
                image_context += f"  Workflow: {' -> '.join(img['analysis']['workflow_steps'])}\n"

    # Extract PKG with image enrichment
    prompt = f"""Extract comprehensive PKG for: "{feature_name}"

This feature is documented across MULTIPLE pages: {page_numbers}

CONTENT FROM ALL PAGES:
{combined_content[:25000]}
{image_context}

Extract COMPLETE PKG structure including information from ALL pages and images.

Return ONLY valid JSON in PKG format:
{{
  "feature_id": "snake_case_id",
  "feature_name": "{feature_name}",
  "page_locations": {page_numbers},

  "ui_surfaces": [
    {{
      "screen_name": "From screenshots/text",
      "navigation_path": "From documentation",
      "page_reference": "Page X"
    }}
  ],

  "inputs": [
    {{
      "name": "Field name from screenshots or text",
      "control_type": "textbox | checkbox | dropdown | button",
      "data_type": "string | integer | boolean",
      "range": "min-max if mentioned",
      "default_value": "default if mentioned",
      "help_text": "Description",
      "location": "Section name",
      "page_reference": "Page X"
    }}
  ],

  "actions": [...],
  "constraints": [...],
  "errors": [...],
  "workflows": [
    {{
      "workflow_id": "workflow_name",
      "steps": ["Step 1", "Step 2"],
      "visual_representation": "From workflow diagram if present",
      "page_reference": "Page X"
    }}
  ],

  "image_insights": [
    {{
      "page": 12,
      "type": "ui_screenshot",
      "insights": "What the image revealed"
    }}
  ]
}}

CRITICAL:
- Consolidate information from ALL pages
- Include insights from image analysis
- Extract field names from screenshots
- Capture workflows from diagrams
- Be comprehensive - this is scattered information unified

Return ONLY valid JSON."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a PKG extraction expert. Extract complete product knowledge from scattered documentation. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_completion_tokens=16000
        )

        result_text = response.choices[0].message.content

        if '```json' in result_text:
            result_text = result_text.split('```json')[1].split('```')[0].strip()
        elif '```' in result_text:
            result_text = result_text.split('```')[1].split('```')[0].strip()

        return json.loads(result_text)

    except Exception as e:
        print(f"[ERROR] PKG extraction failed for {feature_name}: {e}")
        return {}


def main():
    print("=" * 80)
    print("ENHANCED PKG EXTRACTOR: Scattered Features + Image Analysis")
    print("=" * 80)

    # Configuration
    pdf_path = r"c:\Users\SaiShravan.V\OneDrive - Ivanti\Desktop\POC\data\docs\ps-pps-9.1r10.0-profiler-administration-guide.pdf"
    start_page = 1
    end_page = 58

    # IMPORTANT: Change 'admin_guide' to organize by document
    # Example: 'api_guide', 'user_guide', etc.
    document_name = "admin_guide"

    output_dir = Path(r"c:\Users\SaiShravan.V\OneDrive - Ivanti\Desktop\POC\data\pkg") / document_name
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Output directory: {output_dir}")

    # STEP 1: Extract full document
    print(f"\n[STEP 1] Extracting complete PDF (pages {start_page}-{end_page})...")
    pdf_content = extract_pdf_pages(pdf_path, start_page, end_page)
    print(f"[OK] Extracted {len(pdf_content)} characters")

    # STEP 2: Global feature discovery (PHASE 1)
    print(f"\n[STEP 2] Discovering features and their page locations...")
    feature_discovery = discover_features_with_page_locations(pdf_content)

    features = feature_discovery.get('features', [])
    print(f"[OK] Identified {len(features)} features\n")

    # Display discovered features with scattered page info
    for feat in features:
        pages = feat.get('page_locations', [])
        scattered = " [SCATTERED]" if len(pages) > 3 else ""
        print(f"  - {feat['feature_name']}{scattered}")
        print(f"    Pages: {pages}")
        if feat.get('alternative_names'):
            print(f"    Also known as: {', '.join(feat['alternative_names'])}")

    # Save enhanced feature understanding
    feature_understanding_file = output_dir / "feature_understanding_enhanced.json"
    with open(feature_understanding_file, 'w', encoding='utf-8') as f:
        json.dump(feature_discovery, f, indent=2, ensure_ascii=False)

    # STEP 3: Extract images from ALL pages
    print(f"\n[STEP 3] Extracting and analyzing images with Vision model...")
    all_page_numbers = list(range(start_page, end_page + 1))
    images = extract_images_from_pdf(pdf_path, all_page_numbers)
    print(f"[OK] Analyzed {len(images)} images")

    # STEP 4: Extract PKG for each feature from ALL relevant pages (PHASE 2)
    print(f"\n[STEP 4] Extracting PKG from scattered pages...")

    for feature in features:
        feature_name = feature['feature_name']
        page_locations = feature.get('page_locations', [])
        feature_id = feature_name.lower().replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '')

        print(f"\n  -> {feature_name}")
        print(f"     Extracting from pages: {page_locations}")

        # Extract PKG from ALL pages where this feature appears
        pkg = extract_pkg_from_scattered_pages(
            pdf_path,
            feature_name,
            page_locations,
            images
        )

        # Save PKG
        pkg_file = output_dir / f"pkg_{feature_id}.json"
        with open(pkg_file, 'w', encoding='utf-8') as f:
            json.dump(pkg, f, indent=2, ensure_ascii=False)

        print(f"     [OK] PKG saved:")
        print(f"       - {len(pkg.get('inputs', []))} input controls")
        print(f"       - {len(pkg.get('constraints', []))} constraints")
        print(f"       - {len(pkg.get('workflows', []))} workflows")
        print(f"       - {len(pkg.get('image_insights', []))} image insights")

    print(f"\n{'='*80}")
    print(f"[OK] ENHANCED PKG EXTRACTION COMPLETE")
    print(f"  Features with scattered pages: {sum(1 for f in features if len(f.get('page_locations', [])) > 3)}")
    print(f"  Images analyzed: {len(images)}")
    print(f"  Output: {output_dir}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
