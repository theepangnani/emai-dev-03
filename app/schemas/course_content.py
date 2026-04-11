from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from typing import Optional

from app.schemas.user import strip_whitespace

VALID_CONTENT_TYPES = {"notes", "syllabus", "labs", "assignments", "readings", "resources", "other"}


VALID_AI_TOOLS = {"study_guide", "quiz", "flashcards", "none"}

VALID_DOCUMENT_TYPES = {"teacher_notes", "course_syllabus", "past_exam", "mock_exam", "project_brief", "lab_experiment", "textbook_excerpt", "custom", "parent_question", "worksheet", "student_test", "quiz_paper"}
VALID_DETECTED_SUBJECTS = {"math", "science", "english", "french", "history", "geography", "computer_studies", "other"}
VALID_STUDY_GOALS = {"upcoming_test", "final_exam", "assignment", "lab_prep", "general_review", "discussion", "parent_review"}


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
    document_type: Optional[str] = Field(default=None, max_length=30)
    study_goal: Optional[str] = Field(default=None, max_length=30)
    study_goal_text: Optional[str] = Field(default=None, max_length=200)

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

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().lower()
        if normalized not in VALID_DOCUMENT_TYPES:
            raise ValueError(f"Invalid document_type. Must be one of: {', '.join(sorted(VALID_DOCUMENT_TYPES))}")
        return normalized

    @field_validator("study_goal")
    @classmethod
    def validate_study_goal(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().lower()
        if normalized not in VALID_STUDY_GOALS:
            raise ValueError(f"Invalid study_goal. Must be one of: {', '.join(sorted(VALID_STUDY_GOALS))}")
        return normalized


class CourseContentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    text_content: Optional[str] = Field(default=None, max_length=100000)
    content_type: Optional[str] = None
    reference_url: Optional[str] = Field(default=None, max_length=1000)
    google_classroom_url: Optional[str] = Field(default=None, max_length=1000)
    course_id: Optional[int] = None
    category: Optional[str] = Field(default=None, max_length=100)
    display_order: Optional[int] = None
    document_type: Optional[str] = Field(default=None, max_length=30)
    study_goal: Optional[str] = Field(default=None, max_length=30)
    study_goal_text: Optional[str] = Field(default=None, max_length=200)

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

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().lower()
        if normalized not in VALID_DOCUMENT_TYPES:
            raise ValueError(f"Invalid document_type. Must be one of: {', '.join(sorted(VALID_DOCUMENT_TYPES))}")
        return normalized

    @field_validator("study_goal")
    @classmethod
    def validate_study_goal(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().lower()
        if normalized not in VALID_STUDY_GOALS:
            raise ValueError(f"Invalid study_goal. Must be one of: {', '.join(sorted(VALID_STUDY_GOALS))}")
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
    source_files_count: int = 0
    category: Optional[str] = None
    display_order: int = 0
    parent_content_id: Optional[int] = None
    is_master: bool = False
    material_group_id: Optional[int] = None
    source_type: Optional[str] = None
    document_type: Optional[str] = None
    study_goal: Optional[str] = None
    study_goal_text: Optional[str] = None
    # UTDF fields — excluded from default response until DB migration confirmed.
    # Uncomment after ALTER TABLE has run on production PostgreSQL.
    # detected_subject: Optional[str] = None
    # classification_override: Optional[bool] = False
    # subject_confidence: Optional[float] = None
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


class BulkCategorizeRequest(BaseModel):
    content_ids: list[int] = Field(min_length=1)
    category: str = Field(min_length=1, max_length=100)

    @field_validator('category', mode='before')
    @classmethod
    def _strip_category(cls, v: object) -> object:
        return strip_whitespace(v)


class BulkArchiveRequest(BaseModel):
    content_ids: list[int] = Field(min_length=1)


class CourseContentUpdateResponse(CourseContentResponse):
    """Extended response returned from PATCH that includes side-effect counts."""
    archived_guides_count: int = 0


class ReorderSubsRequest(BaseModel):
    sub_ids: list[int] = Field(min_length=1)


class LinkedMaterialResponse(BaseModel):
    """Lightweight representation of a linked material (master or sub)."""
    id: int
    title: str
    is_master: bool = False
    content_type: str
    has_file: bool = False
    original_filename: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ClassificationOverrideRequest(BaseModel):
    document_type: Optional[str] = None
    detected_subject: Optional[str] = None

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().lower()
        if normalized not in VALID_DOCUMENT_TYPES:
            raise ValueError(f"Invalid document_type. Must be one of: {', '.join(sorted(VALID_DOCUMENT_TYPES))}")
        return normalized

    @field_validator("detected_subject")
    @classmethod
    def validate_detected_subject(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        normalized = v.strip().lower()
        if normalized not in VALID_DETECTED_SUBJECTS:
            raise ValueError(f"Invalid detected_subject. Must be one of: {', '.join(sorted(VALID_DETECTED_SUBJECTS))}")
        return normalized


