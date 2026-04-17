"""
ASGF OCR Service — GCP Vision OCR integration for handwritten student notes.

Provides GCP Vision API as an alternative to Anthropic Vision OCR.
Falls back gracefully if google-cloud-vision is not installed or not configured.

Issue: #3410
"""

import base64
import io

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# GCP Vision (optional — requires google-cloud-vision installed)
try:
    from google.cloud import vision  # type: ignore[attr-defined]

    GCP_VISION_AVAILABLE = True
except ImportError:
    GCP_VISION_AVAILABLE = False


def is_gcp_vision_configured() -> bool:
    """Check whether GCP Vision OCR is available and enabled."""
    if not settings.gcp_vision_enabled:
        return False
    if not GCP_VISION_AVAILABLE:
        logger.debug(
            "GCP Vision enabled in config but google-cloud-vision package "
            "is not installed — falling back to Anthropic Vision"
        )
        return False
    return True


async def extract_text_with_gcp_vision(image_bytes: bytes, filename: str) -> str:
    """Use GCP Vision API to OCR handwritten text from images.

    Falls back to existing Anthropic Vision if GCP Vision is not configured.
    Returns extracted text string, or empty string on failure.

    The Vision API client uses Application Default Credentials (ADC), which
    on Cloud Run is the service account automatically. Locally, set
    ``GOOGLE_APPLICATION_CREDENTIALS`` to a service-account JSON key file.
    """
    if not is_gcp_vision_configured():
        return ""

    try:
        import asyncio

        text = await asyncio.to_thread(_sync_extract_text_gcp_vision, image_bytes, filename)
        return text
    except Exception as e:
        logger.warning(
            "GCP Vision OCR failed for %s: %s — will fall back to Anthropic Vision",
            filename,
            e,
        )
        return ""


def _sync_extract_text_gcp_vision(image_bytes: bytes, filename: str) -> str:
    """Synchronous GCP Vision API call (run in a thread pool)."""
    from google.cloud import vision  # type: ignore[attr-defined]

    # Use the Canada endpoint for data residency compliance
    client_options = {"api_endpoint": "northamerica-northeast1-vision.googleapis.com"}
    client = vision.ImageAnnotatorClient(client_options=client_options)

    image = vision.Image(content=image_bytes)

    # Use document_text_detection for best handwriting recognition
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise RuntimeError(
            f"GCP Vision API error: {response.error.message}"
        )

    full_text = response.full_text_annotation.text if response.full_text_annotation else ""

    if full_text.strip():
        logger.info(
            "GCP Vision OCR extracted %d chars from %s",
            len(full_text.strip()),
            filename,
        )
    else:
        logger.info("GCP Vision OCR found no text in %s", filename)

    return full_text.strip()


async def detect_handwriting(image_bytes: bytes) -> bool:
    """Detect if an image likely contains handwriting (vs printed text).

    Uses GCP Vision feature detection when available, otherwise returns False
    (caller should use default OCR path).
    """
    if not is_gcp_vision_configured():
        return False

    try:
        import asyncio

        return await asyncio.to_thread(_sync_detect_handwriting, image_bytes)
    except Exception as e:
        logger.debug("Handwriting detection failed: %s", e)
        return False


def _sync_detect_handwriting(image_bytes: bytes) -> bool:
    """Synchronous handwriting detection via GCP Vision."""
    from google.cloud import vision  # type: ignore[attr-defined]

    client_options = {"api_endpoint": "northamerica-northeast1-vision.googleapis.com"}
    client = vision.ImageAnnotatorClient(client_options=client_options)

    image = vision.Image(content=image_bytes)
    response = client.document_text_detection(image=image)

    if response.error.message:
        return False

    # Check if any pages have a detected handwriting confidence
    # GCP Vision annotates blocks with detected_break and confidence;
    # handwritten text typically has lower confidence and irregular spacing.
    # A simple heuristic: if document_text_detection returns text with
    # page-level confidence below 0.85, it's likely handwritten.
    annotation = response.full_text_annotation
    if not annotation or not annotation.pages:
        return False

    for page in annotation.pages:
        for block in page.blocks:
            if block.confidence and block.confidence < 0.85:
                return True

    return False
