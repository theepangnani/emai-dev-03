"""Schemas for the CB-ONBOARD-001 class-import flow (#3985).

Bulk-create classes+teachers from Google Classroom or a parsed screenshot.
"""
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import strip_whitespace


class BulkCreateRow(BaseModel):
    """One class/teacher row to create during bulk import."""

    class_name: str = Field(min_length=1, max_length=200)
    section: Optional[str] = Field(default=None, max_length=200)
    teacher_name: str = Field(min_length=1, max_length=200)
    teacher_email: Optional[EmailStr] = Field(default=None)
    google_classroom_id: Optional[str] = Field(default=None, max_length=255)

    @field_validator("class_name", "section", "teacher_name", "google_classroom_id", mode="before")
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class BulkCreateRequest(BaseModel):
    rows: list[BulkCreateRow] = Field(min_length=1, max_length=50)


class BulkCreateResult(BaseModel):
    """Top-level response from POST /bulk."""

    created: list[dict]
    failed: list[dict]


class ParsedScreenshotRow(BaseModel):
    class_name: str
    section: Optional[str] = None
    teacher_name: str
    teacher_email: Optional[str] = None


class ParseScreenshotResponse(BaseModel):
    parsed: list[ParsedScreenshotRow]


class GoogleClassroomPreviewCourse(BaseModel):
    class_name: str
    section: Optional[str] = None
    teacher_name: Optional[str] = None
    teacher_email: Optional[str] = None
    google_classroom_id: str
    existing: bool = False
    existing_course_id: Optional[int] = None


class GoogleClassroomPreviewResponse(BaseModel):
    connected: bool
    connect_url: Optional[str] = None
    error: Optional[str] = None
    courses: list[GoogleClassroomPreviewCourse] = Field(default_factory=list)
