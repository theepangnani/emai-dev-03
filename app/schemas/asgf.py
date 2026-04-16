"""Pydantic schemas for the AI Study Guide Factory (ASGF)."""

from typing import Any, Literal, Optional

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


# --- Context assembly & learning cycle plan (from #3396) ---

class ContextPackage(BaseModel):
    """Structured input assembled for plan generation."""

    question: str
    subject: str = ""
    grade_level: str = ""
    topic: str = ""
    bloom_entry_point: str = ""
    concepts: list[dict] = Field(default_factory=list)
    gap_data: dict = Field(default_factory=dict)
    document_metadata: list[dict] = Field(default_factory=list)
    student_profile: dict = Field(default_factory=dict)
    classroom_context: dict = Field(default_factory=dict)
    session_metadata: dict = Field(default_factory=dict)


class SlidePlanItem(BaseModel):
    """A single slide in the learning cycle plan."""

    title: str
    brief: str
    bloom_tier: str = ""


class QuizPlanItem(BaseModel):
    """A single quiz question in the learning cycle plan."""

    bloom_tier: str
    format: str  # e.g. "multiple_choice", "short_answer", "true_false"
    topic: str
    difficulty: str  # "easy", "medium", "hard"


class LearningCyclePlan(BaseModel):
    """Structured output from Claude plan generation."""

    topic_classification: dict = Field(
        default_factory=dict,
        description="subject, grade_level, bloom_entry_point",
    )
    core_concepts: list[str] = Field(
        default_factory=list,
        description="3-5 key concepts",
    )
    prerequisite_check: dict = Field(
        default_factory=dict,
        description="known vs needs-establishing",
    )
    slide_plan: list[SlidePlanItem] = Field(default_factory=list)
    direct_answer_outline: dict = Field(
        default_factory=dict,
        description="Structure of the answer",
    )
    sample_plan: list[dict] = Field(
        default_factory=list,
        description="2-3 worked examples",
    )
    quiz_plan: list[QuizPlanItem] = Field(default_factory=list)
    estimated_session_time_min: int = 12


class CreateSessionRequest(BaseModel):
    """Request to create a new ASGF session."""

    question: str = Field(..., min_length=1, max_length=2000)
    file_ids: list[str] = Field(default_factory=list)
    child_id: str | None = None
    subject: str | None = None
    grade: str | None = None
    course_id: str | None = None


class CreateSessionResponse(BaseModel):
    """Response after session creation with plan preview."""

    session_id: str
    topic: str
    subject: str
    grade_level: str
    slide_count: int
    quiz_count: int
    estimated_time_min: int


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


# --- Comprehension signal (#3399) ---

class ComprehensionSignalRequest(BaseModel):
    slide_number: int = Field(..., ge=0)
    signal: Literal["got_it", "still_confused"]


class ComprehensionSignalResponse(BaseModel):
    acknowledged: bool = True
    re_explanation_slide: Optional[dict[str, Any]] = None
