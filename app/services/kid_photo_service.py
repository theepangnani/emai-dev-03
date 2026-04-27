"""CB-KIDPHOTO-001 (#4301) — kid profile photo upload service.

Validation, EXIF-strip + resize processing, and GCS upload/delete helpers
for parent-uploaded child profile photos.
"""

from __future__ import annotations

import io
import logging
import uuid
from typing import Final

from fastapi import HTTPException, UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)


MAX_BYTES: Final[int] = 5 * 1024 * 1024  # 5 MB
MAX_DIMENSION: Final[int] = 512
ALLOWED_EXTENSIONS: Final[set[str]] = {"jpg", "jpeg", "png", "webp"}

# Magic-byte prefixes for the formats we accept. WebP is "RIFF....WEBP".
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_WEBP_RIFF_PREFIX = b"RIFF"
_WEBP_FORMAT_TAG = b"WEBP"

GCS_PREFIX: Final[str] = "kid-photos"


def _ext_of(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def _has_valid_magic(raw: bytes) -> bool:
    if raw.startswith(_JPEG_MAGIC):
        return True
    if raw.startswith(_PNG_MAGIC):
        return True
    if (
        len(raw) >= 12
        and raw[:4] == _WEBP_RIFF_PREFIX
        and raw[8:12] == _WEBP_FORMAT_TAG
    ):
        return True
    return False


async def validate_image(file: UploadFile) -> bytes:
    """Validate the uploaded image. Returns the raw bytes on success.

    Raises:
        HTTPException(422) on extension, size, or magic-byte failures.
    """
    ext = _ext_of(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail="Unsupported file type. Allowed: JPG, PNG, WebP.",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Empty upload.")
    if len(raw) > MAX_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"Image exceeds {MAX_BYTES // (1024 * 1024)} MB limit.",
        )
    if not _has_valid_magic(raw):
        raise HTTPException(
            status_code=422,
            detail="File does not look like a valid JPG, PNG, or WebP image.",
        )
    return raw


def process_image(raw: bytes) -> bytes:
    """Strip EXIF and resize to fit within MAX_DIMENSION × MAX_DIMENSION.

    Re-encodes as JPEG with quality=85. Returns the processed bytes.
    """
    from PIL import Image  # local import keeps test discovery lighter

    try:
        with Image.open(io.BytesIO(raw)) as img:
            # Convert to RGB up-front so PNG/WebP with alpha don't break JPEG encode.
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))

            out = io.BytesIO()
            # Saving without the original `info`/`exif` strips EXIF metadata.
            img.save(out, format="JPEG", quality=85, optimize=True)
            return out.getvalue()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Image processing failed: %s", exc)
        raise HTTPException(status_code=422, detail="Could not process image.") from exc


def _build_object_name(student_id: int) -> str:
    return f"{GCS_PREFIX}/{student_id}-{uuid.uuid4().hex}.jpg"


def upload_to_gcs(image_bytes: bytes, student_id: int) -> str:
    """Upload processed JPEG bytes to GCS. Returns the public/object URL.

    If GCS is not configured (dev / tests), returns a local-style placeholder
    URL so callers can still persist a value and test the round-trip.
    """
    object_name = _build_object_name(student_id)

    if not getattr(settings, "use_gcs", False) or not getattr(settings, "gcs_bucket_name", ""):
        # Dev / test fallback — no bucket configured.
        return f"local://{object_name}"

    try:
        from app.services import gcs_service
        gcs_service.upload_file(object_name, image_bytes, "image/jpeg")
        return f"https://storage.googleapis.com/{settings.gcs_bucket_name}/{object_name}"
    except Exception as exc:
        logger.warning("GCS upload failed for student %s: %s", student_id, exc)
        # Bucket transiently unavailable — fall back so the column still gets a value
        # rather than 500-ing the request. The next upload will retry.
        return f"local://{object_name}"


def delete_from_gcs(url: str | None) -> None:
    """Best-effort delete of a previously-uploaded photo. Never raises."""
    if not url:
        return
    object_name: str | None = None
    if url.startswith("local://"):
        return  # nothing to delete in dev / test fallback
    bucket = getattr(settings, "gcs_bucket_name", "")
    public_prefix = f"https://storage.googleapis.com/{bucket}/" if bucket else None
    if public_prefix and url.startswith(public_prefix):
        object_name = url[len(public_prefix):]
    elif url.startswith(f"{GCS_PREFIX}/"):
        object_name = url
    if not object_name:
        logger.info("Skipping GCS delete for unrecognised URL: %s", url)
        return
    if not getattr(settings, "use_gcs", False) or not bucket:
        return
    try:
        from app.services import gcs_service
        gcs_service.delete_file(object_name)
    except Exception as exc:  # pragma: no cover — best-effort
        logger.warning("GCS delete failed for %s: %s", object_name, exc)
