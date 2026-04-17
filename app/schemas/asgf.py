"""Pydantic schemas for the AI Study Guide Factory (ASGF)."""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- Intent classification (from #3413) ---

class IntentClassifyRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class IntentAlternative(BaseModel):
    subject: str = ""
    topic: str = ""
    confidence: float = 0.0


class IntentClassifyResponse(BaseModel):
    subject: str = ""
    grade_level: str = ""
    topic: str = ""
    confidence: float = 0.0
    bloom_tier: str = ""
    alternatives: list[IntentAlternative] = Field(default_factory=list)


# --- File upload (from #3411) ---

class FileUploadResponse(BaseModel):
    """Metadata for a single uploaded file."""

    file_id: str
    filename: str
    file_type: str
    file_size_bytes: int
    text_preview: str
    extraction_failed: bool = False

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


class StudentProfile(BaseModel):
    """Typed student profile for ContextPackage."""

    grade: str = ""
    board: str = ""
    school: str = ""


class ClassroomContext(BaseModel):
    """Typed classroom context for ContextPackage."""

    course_name: str = ""
    teacher: str = ""
    subject: str = ""


class GapData(BaseModel):
    """Typed gap analysis data for ContextPackage."""

    weak_topics: list[str] = Field(default_factory=list)
    previously_studied: list[str] = Field(default_factory=list)


class ContextPackage(BaseModel):
    """Structured input assembled for plan generation."""

    question: str
    subject: str = ""
    grade_level: str = ""
    topic: str = ""
    bloom_entry_point: str = ""
    concepts: list[dict] = Field(default_factory=list)
    gap_data: GapData = Field(default_factory=GapData)
    document_metadata: list[dict] = Field(default_factory=list)
    student_profile: StudentProfile = Field(default_factory=StudentProfile)
    classroom_context: ClassroomContext = Field(default_factory=ClassroomContext)
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
    re_explanation_slide: Optional[ASGFSlideResponse] = None


# --- Quiz bridge (#3400) ---

class ASGFQuizQuestion(BaseModel):
    """A single slide-anchored quiz question."""

    question_text: str
    options: list[str] = Field(..., min_length=4, max_length=4)
    correct_index: int = Field(..., ge=0, le=3)
    bloom_tier: str
    slide_reference: int = Field(..., ge=0)
    hint_text: str
    explanation: str


class ASGFQuizResponse(BaseModel):
    """Quiz questions generated for an ASGF session."""

    session_id: str
    questions: list[ASGFQuizQuestion]


# --- Session completion / auto-save (#3401) ---

class QuizResultItem(BaseModel):
    question_text: str
    correct: bool
    attempts: int = Field(..., ge=1)
    xp_earned: int = Field(..., ge=0)


class CompleteSessionRequest(BaseModel):
    quiz_results: list[QuizResultItem] = Field(..., min_length=1)


class CompleteSessionResponse(BaseModel):
    material_id: int
    summary: str


# --- Assignment options (#3402) ---

class AssignmentOption(BaseModel):
    key: str
    label: str
    description: str


class CourseSuggestion(BaseModel):
    course_id: str | None = None
    course_name: str | None = None
    confidence: float = 0.0


class AssignmentOptionsResponse(BaseModel):
    role: str
    options: list[AssignmentOption]
    suggested_course: CourseSuggestion | None = None


class AssignRequest(BaseModel):
    assignment_type: Literal["private", "share_teacher", "share_parent", "review_task", "submit_teacher"] = Field(...)
    course_id: str | None = None
    due_date: str | None = None

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v):
        if v is not None:
            from datetime import date
            try:
                date.fromisoformat(v)
            except ValueError:
                raise ValueError("due_date must be in ISO format (YYYY-MM-DD)")
        return v


class AssignResponse(BaseModel):
    success: bool
    message: str


# --- Spaced repetition / review topics (#3403) ---

class ReviewTopicItem(BaseModel):
    session_id: str
    subject: str
    topic: str
    score_pct: int | None = None
    weak_concepts: list[str] = Field(default_factory=list)
    days_since_last: int
    review_interval: int
    last_session_date: str


class ReviewTopicsResponse(BaseModel):
    student_id: int
    topics: list[ReviewTopicItem]


# --- ASGF usage / session cap (#3405) ---

class ASGFUsageResponse(BaseModel):
    used: int
    limit: int
    remaining: int
    can_start: bool


# --- Session resume (#3409) ---

class ResumeSessionResponse(BaseModel):
    session_id: str
    current_slide_index: int
    signals_given: list[dict] = Field(default_factory=list)
    quiz_progress: list[dict] = Field(default_factory=list)
    slides: list[dict] = Field(default_factory=list)
    created_at: str
    expires_at: str


class ActiveSessionItem(BaseModel):
    session_id: str
    question: str
    subject: str
    created_at: str
    slide_count: int


class ActiveSessionsResponse(BaseModel):
    sessions: list[ActiveSessionItem]
