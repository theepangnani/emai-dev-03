"""Pydantic schemas for the AI Study Guide Factory (ASGF)."""

from pydantic import BaseModel, ConfigDict, Field


# --- Intent classification (from #3413) ---

class IntentClassifyRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class IntentClassifyResponse(BaseModel):
    subject: str = ""
    grade_level: str = ""
    topic: str = ""
    confidence: float = 0.0
    bloom_tier: str = ""


# --- File upload (from #3411) ---

class FileUploadResponse(BaseModel):
    """Metadata for a single uploaded file."""

    file_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    text_preview: str

    model_config = ConfigDict(from_attributes=True)


class MultiFileUploadResponse(BaseModel):
    """Response for a multi-file upload request."""

    files: list[FileUploadResponse]
    total_size_bytes: int

    model_config = ConfigDict(from_attributes=True)


# --- Context panel (from #3412) ---

class ChildItem(BaseModel):
    id: str
    name: str
    grade: str
    board: str

    model_config = ConfigDict(from_attributes=True)


class CourseItem(BaseModel):
    id: str
    name: str
    teacher: str

    model_config = ConfigDict(from_attributes=True)


class TaskItem(BaseModel):
    id: str
    title: str
    due_date: str

    model_config = ConfigDict(from_attributes=True)


class ASGFContextDataResponse(BaseModel):
    children: list[ChildItem]
    courses: list[CourseItem]
    upcoming_tasks: list[TaskItem]


# --- Slide generation (from #3398) ---

class ASGFSlideRequest(BaseModel):
    """Request body for the slide generation SSE endpoint."""

    learning_cycle_plan: dict = Field(
        ..., description="Output from asgf_service.generate_learning_cycle_plan()"
    )
    context_package: dict = Field(
        ..., description="Output from asgf_ingestion_service.process_documents()"
    )


class ASGFSlideResponse(BaseModel):
    """A single generated slide."""

    slide_number: int
    title: str
    body: str
    vocabulary_terms: list[str] = Field(default_factory=list)
    source_attribution: str | None = None
    read_more_content: str | None = None
    bloom_tier: str = "understand"

    model_config = ConfigDict(from_attributes=True)
