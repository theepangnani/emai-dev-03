import re
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

# 50 MB max content size (base64 images inline in HTML)
MAX_CONTENT_SIZE = 50 * 1024 * 1024
MAX_IMAGES_PER_NOTE = 10
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

# Regex patterns for image validation
_IMG_TAG_RE = re.compile(r"<img\s", re.IGNORECASE)
_DATA_URI_RE = re.compile(
    r'src="data:(image/(?:jpeg|png|gif|webp));base64,([^"]+)"',
    re.IGNORECASE,
)


def _count_images(html: str) -> int:
    """Count <img tags in HTML content."""
    return len(_IMG_TAG_RE.findall(html))


def _has_images(html: str | None) -> bool:
    """Check if HTML content contains <img tags."""
    if not html:
        return False
    return bool(_IMG_TAG_RE.search(html))


class NoteUpsert(BaseModel):
    """Schema for creating or updating a note (PUT upsert)."""
    content: Optional[str] = Field(default=None, description="Rich HTML content")
    plain_text: Optional[str] = Field(default=None, description="Plain text for search")

    @field_validator("content")
    @classmethod
    def validate_content_size(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.encode("utf-8")) > MAX_CONTENT_SIZE:
            raise ValueError(f"Content size exceeds {MAX_CONTENT_SIZE // (1024 * 1024)} MB limit")
        return v

    @field_validator("content")
    @classmethod
    def validate_image_count(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and _count_images(v) > MAX_IMAGES_PER_NOTE:
            raise ValueError(f"Maximum {MAX_IMAGES_PER_NOTE} images per note")
        return v


class NoteResponse(BaseModel):
    id: int
    user_id: int
    course_content_id: int
    content: Optional[str] = None
    plain_text: Optional[str] = None
    has_images: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NoteListItem(BaseModel):
    """Lightweight response for listing notes (no full content)."""
    id: int
    user_id: int
    course_content_id: int
    has_images: bool = False
    plain_text_preview: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
