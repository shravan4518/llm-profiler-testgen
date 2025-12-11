"""
Image Processor for Multimodal RAG
Extracts images from PDFs and uses Vision LLM to generate searchable descriptions
"""
import sys
import io
import base64
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from PIL import Image

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Try to import Vision LLM packages
try:
    import google.generativeai as genai
    GEMINI_VISION_AVAILABLE = True
except ImportError:
    GEMINI_VISION_AVAILABLE = False
    logger.warning("google-generativeai not installed. Multimodal features will be limited.")


class ImageProcessor:
    """
    Processes images from PDF documents using Vision LLM

    Extracts images, filters by size, and generates detailed text descriptions
    that can be embedded and searched alongside document text.
    """

    def __init__(self):
        """Initialize Image Processor with Vision LLM"""
        self.vision_model = None

        if not config.ENABLE_IMAGE_PROCESSING:
            logger.info("Image processing is disabled in config")
            return

        if not GEMINI_VISION_AVAILABLE:
            logger.warning("Gemini Vision not available. Install: pip install google-generativeai pillow")
            return

        # Initialize Gemini Vision
        try:
            genai.configure(api_key=config.GEMINI_API_KEY)
            self.vision_model = genai.GenerativeModel(config.IMAGE_VISION_MODEL)
            logger.info(f"Vision LLM initialized: {config.IMAGE_VISION_MODEL}")
        except Exception as e:
            logger.error(f"Failed to initialize Vision LLM: {e}")
            self.vision_model = None

    def extract_images_from_pdf(self, pdf_path: str) -> Dict[int, List[Image.Image]]:
        """
        Extract images from PDF using pdfplumber

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary mapping page_number -> list of PIL Images
        """
        import pdfplumber

        images_by_page = {}

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_images = []

                    # Get images from page
                    if hasattr(page, 'images') and page.images:
                        for img_info in page.images[:config.MAX_IMAGES_PER_PAGE]:
                            try:
                                # Extract image
                                image = page.within_bbox(
                                    (img_info['x0'], img_info['top'],
                                     img_info['x1'], img_info['bottom'])
                                ).to_image()

                                # Convert to PIL Image
                                pil_image = image.original

                                # Filter by size (skip icons/logos)
                                width, height = pil_image.size
                                if width >= config.IMAGE_MIN_SIZE and height >= config.IMAGE_MIN_SIZE:
                                    page_images.append(pil_image)
                                    logger.debug(f"Extracted image from page {page_num}: {width}x{height}")

                            except Exception as e:
                                logger.warning(f"Could not extract image from page {page_num}: {e}")
                                continue

                    if page_images:
                        images_by_page[page_num] = page_images
                        logger.info(f"Page {page_num}: Extracted {len(page_images)} images")

            total_images = sum(len(imgs) for imgs in images_by_page.values())
            logger.info(f"Total images extracted from PDF: {total_images} across {len(images_by_page)} pages")

        except Exception as e:
            logger.error(f"Error extracting images from PDF: {e}")

        return images_by_page

    def image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string"""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def analyze_image_with_vision_llm(self, image: Image.Image, page_context: str = "", retry_count: int = 0) -> Optional[str]:
        """
        Analyze image using Vision LLM and generate detailed description
        Includes automatic retry for rate limits and error handling for safety blocks

        Args:
            image: PIL Image object
            page_context: Surrounding text context from the page (optional)
            retry_count: Number of retries attempted (for rate limiting)

        Returns:
            Text description of the image
        """
        if not self.vision_model:
            logger.warning("Vision LLM not initialized")
            return None

        try:
            # Build simplified prompt for better compatibility
            prompt = f"""Describe this technical documentation image. Include:
- Image type (screenshot/diagram/flowchart)
- Visible UI elements or components
- Any text or labels shown
- Technical details

Keep description factual and concise."""

            # Send image and prompt to Vision LLM
            logger.debug("Sending image to Vision LLM for analysis...")

            # Add safety settings to reduce blocks
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]

            response = self.vision_model.generate_content(
                [prompt, image],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,  # Very low temperature for factual descriptions
                    max_output_tokens=config.IMAGE_DESCRIPTION_MAX_TOKENS
                ),
                safety_settings=safety_settings
            )

            # Handle response with safety block checking
            if response:
                try:
                    description = response.text.strip()
                    logger.info(f"Generated image description ({len(description)} chars)")
                    return f"\n\n[IMAGE DESCRIPTION]\n{description}\n\n"
                except ValueError as e:
                    # Check for safety block
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'finish_reason') and candidate.finish_reason == 2:
                            logger.warning("Image blocked by safety filters")
                            return None  # Use fallback
                    raise

            logger.warning("Vision LLM returned empty response")
            return None

        except Exception as e:
            error_msg = str(e)

            # Handle rate limit errors with retry
            if "429" in error_msg or "quota" in error_msg.lower():
                if retry_count < 2:  # Max 2 retries
                    # Extract retry delay from error
                    wait_time = 15  # Default wait time
                    if "retry in" in error_msg:
                        try:
                            wait_time = int(float(error_msg.split("retry in ")[1].split("s")[0])) + 1
                        except:
                            pass

                    logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry {retry_count + 1}/2...")
                    time.sleep(wait_time)
                    return self.analyze_image_with_vision_llm(image, page_context, retry_count + 1)
                else:
                    logger.error(f"Rate limit exceeded after retries: {e}")
                    return None

            # Log other errors
            logger.error(f"Error analyzing image with Vision LLM: {e}")
            return None

    def process_pdf_images(
        self,
        pdf_path: str,
        page_texts: Dict[int, str]
    ) -> Dict[int, List[str]]:
        """
        Extract and analyze all images from a PDF

        Args:
            pdf_path: Path to PDF file
            page_texts: Dictionary mapping page_number -> text content

        Returns:
            Dictionary mapping page_number -> list of image descriptions
        """
        if not config.ENABLE_IMAGE_PROCESSING:
            logger.debug("Image processing disabled, skipping")
            return {}

        if not self.vision_model:
            logger.warning("Vision LLM not available, skipping image processing")
            return {}

        logger.info(f"Processing images from: {pdf_path}")

        # Extract images
        images_by_page = self.extract_images_from_pdf(pdf_path)

        if not images_by_page:
            logger.info("No images found in PDF")
            return {}

        # Analyze each image
        descriptions_by_page = {}

        for page_num, images in images_by_page.items():
            page_descriptions = []
            page_context = page_texts.get(page_num, "")

            logger.info(f"Analyzing {len(images)} images from page {page_num}...")

            for img_idx, image in enumerate(images, 1):
                logger.debug(f"Processing image {img_idx}/{len(images)} on page {page_num}")

                # Analyze image
                description = self.analyze_image_with_vision_llm(image, page_context)

                if description:
                    # Format description for insertion into text
                    formatted_desc = f"\n\n{description}\n\n"
                    page_descriptions.append(formatted_desc)
                else:
                    # Fallback description if Vision LLM fails
                    fallback = f"\n\n[IMAGE: Figure {img_idx} on page {page_num}]\n\n"
                    page_descriptions.append(fallback)
                    logger.warning(f"Using fallback description for image {img_idx} on page {page_num}")

                # Throttle to respect free tier rate limit (10 requests/minute)
                # Wait 6 seconds between images to stay under limit
                if img_idx < len(images):  # Don't wait after last image on page
                    logger.debug("Waiting 6s to respect API rate limit...")
                    time.sleep(6)

            descriptions_by_page[page_num] = page_descriptions
            logger.info(f"Page {page_num}: Generated {len(page_descriptions)} image descriptions")

        total_descriptions = sum(len(descs) for descs in descriptions_by_page.values())
        logger.info(f"Image processing complete: {total_descriptions} descriptions generated")

        return descriptions_by_page

    def is_available(self) -> bool:
        """Check if image processing is available"""
        return (config.ENABLE_IMAGE_PROCESSING and
                GEMINI_VISION_AVAILABLE and
                self.vision_model is not None)


def integrate_image_descriptions(
    text_content: str,
    page_texts: Dict[int, str],
    image_descriptions: Dict[int, List[str]]
) -> str:
    """
    Integrate image descriptions into document text

    Args:
        text_content: Full document text
        page_texts: Text content by page
        image_descriptions: Image descriptions by page

    Returns:
        Enhanced text with image descriptions inserted
    """
    if not image_descriptions:
        return text_content

    enhanced_content = text_content

    # Insert image descriptions at page boundaries
    for page_num in sorted(image_descriptions.keys()):
        page_marker = f"--- Page {page_num} ---"

        if page_marker in enhanced_content:
            # Find position after page marker
            marker_pos = enhanced_content.find(page_marker) + len(page_marker)

            # Insert all image descriptions for this page
            for description in image_descriptions[page_num]:
                enhanced_content = (
                    enhanced_content[:marker_pos] +
                    description +
                    enhanced_content[marker_pos:]
                )
                marker_pos += len(description)

    return enhanced_content
