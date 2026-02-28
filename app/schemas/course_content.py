from pydantic import BaseModel, field_validator, model_validator
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
    course_id: Optional[int] = None

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
