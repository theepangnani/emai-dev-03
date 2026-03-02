from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from typing import Optional

from app.schemas.user import strip_whitespace

VALID_CONTENT_TYPES = {"notes", "syllabus", "labs", "assignments", "readings", "resources", "other"}

# Valid material types for #666 type classification
VALID_MATERIAL_TYPES = {"notes", "test", "lab", "assignment", "report_card"}
# Material types that are assessments (trigger is_assessment flag)
ASSESSMENT_MATERIAL_TYPES = {"test"}


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
    material_type: Optional[str] = None
    is_assessment: bool = False
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
    ai_suggested: bool = True
    created_at: datetime
    updated_at: Optional[datetime]
    archived_at: Optional[datetime] = None
    last_viewed_at: Optional[datetime] = None

    @model_validator(mode="after")
    def compute_derived_fields(self):
        self.has_file = self.file_path is not None
        # is_assessment stored as int in SQLite; coerce to bool
        if isinstance(self.is_assessment, int):
            self.is_assessment = bool(self.is_assessment)
        # report_card type: no AI suggestion
        if self.material_type == "report_card":
            self.ai_suggested = False
        return self

    class Config:
        from_attributes = True


class CourseContentUpdateResponse(CourseContentResponse):
    """Extended response returned from PATCH that includes side-effect counts."""
    archived_guides_count: int = 0


# --- Task Extraction Schemas (#878) ---

class ExtractedTaskItem(BaseModel):
    """A single task extracted by AI from a document."""
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None  # ISO date string YYYY-MM-DD
    priority: str = "medium"  # low, medium, high
    included: bool = True  # frontend toggle


class ExtractTasksResponse(BaseModel):
    """Response from the extract-tasks endpoint."""
    content_id: int
    filename: Optional[str] = None
    tasks: list[ExtractedTaskItem]
    message: str


class TaskCreateFromExtraction(BaseModel):
    """A single task to create from extraction results."""
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None  # ISO date string YYYY-MM-DD
    priority: str = "medium"
    assigned_to_user_id: Optional[int] = None


class BulkTaskCreateRequest(BaseModel):
    """Request to create multiple tasks from extraction."""
    tasks: list[TaskCreateFromExtraction]


class CreatedTaskSummary(BaseModel):
    """Summary of a created task."""
    id: int
    title: str
    due_date: Optional[str] = None
    priority: str


class BulkTaskCreateResponse(BaseModel):
    """Response from the create-tasks endpoint."""
    created_count: int
    tasks: list[CreatedTaskSummary]
