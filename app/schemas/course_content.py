from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional

VALID_CONTENT_TYPES = {"notes", "syllabus", "labs", "assignments", "readings", "resources", "other"}


class CourseContentCreate(BaseModel):
    course_id: int
    title: str
    description: Optional[str] = None
    text_content: Optional[str] = None
    content_type: str = "other"
    reference_url: Optional[str] = None
    google_classroom_url: Optional[str] = None

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in VALID_CONTENT_TYPES:
            raise ValueError(f"Invalid content_type. Must be one of: {', '.join(sorted(VALID_CONTENT_TYPES))}")
        return normalized


class CourseContentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    text_content: Optional[str] = None
    content_type: Optional[str] = None
    reference_url: Optional[str] = None
    google_classroom_url: Optional[str] = None

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().lower()
        if normalized not in VALID_CONTENT_TYPES:
            raise ValueError(f"Invalid content_type. Must be one of: {', '.join(sorted(VALID_CONTENT_TYPES))}")
        return normalized


class CourseContentResponse(BaseModel):
    id: int
    course_id: int
    course_name: Optional[str] = None
    title: str
    description: Optional[str]
    text_content: Optional[str] = None
    content_type: str
    reference_url: Optional[str]
    google_classroom_url: Optional[str]
    created_by_user_id: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
