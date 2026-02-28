from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from typing import Optional

from app.schemas.user import strip_whitespace

VALID_CONTENT_TYPES = {"notes", "syllabus", "labs", "assignments", "readings", "resources", "other"}


VALID_AI_TOOLS = {"study_guide", "quiz", "flashcards", "none"}


class CourseContentCreate(BaseModel):
    course_id: int
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    text_content: Optional[str] = Field(default=None, max_length=100000)
    content_type: str = "other"
    reference_url: Optional[str] = Field(default=None, max_length=1000)
    google_classroom_url: Optional[str] = Field(default=None, max_length=1000)
    ai_tool: Optional[str] = Field(default="none", max_length=20)
    ai_custom_prompt: Optional[str] = Field(default=None, max_length=2000)

    @field_validator('title', 'description', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in VALID_CONTENT_TYPES:
            raise ValueError(f"Invalid content_type. Must be one of: {', '.join(sorted(VALID_CONTENT_TYPES))}")
        return normalized

    @field_validator("ai_tool")
    @classmethod
    def validate_ai_tool(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return "none"
        normalized = v.strip().lower()
        if normalized not in VALID_AI_TOOLS:
            raise ValueError(f"Invalid ai_tool. Must be one of: {', '.join(sorted(VALID_AI_TOOLS))}")
        return normalized


class CourseContentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    text_content: Optional[str] = Field(default=None, max_length=100000)
    content_type: Optional[str] = None
    reference_url: Optional[str] = Field(default=None, max_length=1000)
    google_classroom_url: Optional[str] = Field(default=None, max_length=1000)
    course_id: Optional[int] = None

    @field_validator('title', 'description', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)

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
    created_by_user_id: Optional[int] = None
    google_classroom_material_id: Optional[str] = None
    file_path: Optional[str] = None
    original_filename: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    has_file: bool = False
    download_restricted: bool = False
    created_at: datetime
    updated_at: Optional[datetime]
    archived_at: Optional[datetime] = None
    last_viewed_at: Optional[datetime] = None

    @model_validator(mode="after")
    def compute_has_file(self):
        self.has_file = self.file_path is not None
        return self

    class Config:
        from_attributes = True


class CourseContentUpdateResponse(CourseContentResponse):
    """Extended response returned from PATCH that includes side-effect counts."""
    archived_guides_count: int = 0
