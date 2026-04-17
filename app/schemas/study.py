from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Any

from app.schemas.user import strip_whitespace


class StudyGuideCreate(BaseModel):
    """Request to generate a study guide."""
    assignment_id: int | None = None
    course_id: int | None = None
    course_content_id: int | None = None
    title: str | None = Field(default=None, max_length=200)  # Optional custom title
    content: str | None = Field(default=None, max_length=50000)  # Optional custom content to base guide on
    regenerate_from_id: int | None = None  # ID of existing guide to create new version of
    custom_prompt: str | None = Field(default=None, max_length=5000)  # Custom AI prompt (for "Other" tool selection)
    focus_prompt: str | None = Field(default=None, max_length=2000)  # Optional focus area for AI generation
    document_type: str | None = Field(default=None, max_length=30)  # Auto-detected or user-selected document type (§6.105)
    study_goal: str | None = Field(default=None, max_length=30)  # Study goal selection (§6.105)
    study_goal_text: str | None = Field(default=None, max_length=200)  # Free-text study goal details (§6.105)

    @field_validator('title', 'custom_prompt', 'focus_prompt', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class AutoCreatedTask(BaseModel):
    """Summary of an auto-created task."""
    id: int
    title: str
    due_date: str
    priority: str


class StudyGuideResponse(BaseModel):
    """Study guide response."""
    id: int
    user_id: int
    assignment_id: int | None
    course_id: int | None
    course_content_id: int | None = None
    title: str
    content: str
    guide_type: str
    version: int = 1
    parent_guide_id: int | None = None
    relationship_type: str | None = None
    generation_context: str | None = None
    focus_prompt: str | None = None
    is_truncated: bool = False
    parent_summary: str | None = None
    curriculum_codes: str | None = None  # JSON string
    suggestion_topics: str | None = None
    answer_key_markdown: str | None = None
    weak_topics: str | None = None
    ai_engine: str | None = None
    created_at: datetime
    archived_at: datetime | None = None
    safety_checked: bool = True
    auto_created_tasks: list[AutoCreatedTask] = []

    # Sharing fields
    shared_with_user_id: int | None = None
    shared_at: datetime | None = None
    viewed_at: datetime | None = None
    viewed_count: int = 0
    shared_with_name: str | None = None

    class Config:
        from_attributes = True


class AnswerKeyResponse(BaseModel):
    """Response after generating an answer key for a worksheet."""
    id: int
    title: str
    guide_type: str
    answer_key_markdown: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class QuizGenerateRequest(BaseModel):
    """Request to generate a quiz."""
    assignment_id: int | None = None
    course_id: int | None = None
    course_content_id: int | None = None
    topic: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=50000)
    num_questions: int = Field(default=5, ge=1, le=50)
    regenerate_from_id: int | None = None
    focus_prompt: str | None = Field(default=None, max_length=2000)  # Optional focus area for AI generation
    difficulty: str | None = Field(default=None, max_length=10)  # easy, medium, hard
    document_type: str | None = Field(default=None, max_length=30)  # §6.106: inherited on regeneration
    study_goal: str | None = Field(default=None, max_length=30)
    study_goal_text: str | None = Field(default=None, max_length=200)

    @field_validator('topic', 'focus_prompt', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)

    @field_validator('difficulty', mode='before')
    @classmethod
    def _validate_difficulty(cls, v: object) -> object:
        if v is None:
            return None
        s = str(v).lower().strip()
        if s not in ('easy', 'medium', 'hard'):
            raise ValueError('difficulty must be easy, medium, or hard')
        return s


class QuizQuestion(BaseModel):
    """A single quiz question."""
    question: str
    options: dict[str, str]  # {"A": "...", "B": "...", ...}
    correct_answer: str
    explanation: str


class QuizResponse(BaseModel):
    """Quiz response with questions."""
    id: int
    title: str
    questions: list[QuizQuestion]
    guide_type: str = "quiz"
    course_content_id: int | None = None
    version: int = 1
    parent_guide_id: int | None = None
    created_at: datetime
    safety_checked: bool = True
    auto_created_tasks: list[AutoCreatedTask] = []

    class Config:
        from_attributes = True


class FlashcardGenerateRequest(BaseModel):
    """Request to generate flashcards."""
    assignment_id: int | None = None
    course_id: int | None = None
    course_content_id: int | None = None
    topic: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=50000)
    num_cards: int = Field(default=10, ge=1, le=50)
    regenerate_from_id: int | None = None
    focus_prompt: str | None = Field(default=None, max_length=2000)  # Optional focus area for AI generation
    document_type: str | None = Field(default=None, max_length=30)  # §6.106: inherited on regeneration
    study_goal: str | None = Field(default=None, max_length=30)
    study_goal_text: str | None = Field(default=None, max_length=200)

    @field_validator('topic', 'focus_prompt', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class Flashcard(BaseModel):
    """A single flashcard."""
    front: str
    back: str


class FlashcardSetResponse(BaseModel):
    """Flashcard set response."""
    id: int
    title: str
    cards: list[Flashcard]
    guide_type: str = "flashcards"
    course_content_id: int | None = None
    version: int = 1
    parent_guide_id: int | None = None
    created_at: datetime
    safety_checked: bool = True
    auto_created_tasks: list[AutoCreatedTask] = []

    class Config:
        from_attributes = True


class MindMapGenerateRequest(BaseModel):
    """Request to generate a mind map."""
    assignment_id: int | None = None
    course_id: int | None = None
    course_content_id: int | None = None
    topic: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=50000)
    regenerate_from_id: int | None = None
    focus_prompt: str | None = Field(default=None, max_length=2000)

    @field_validator('topic', 'focus_prompt', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class MindMapBranch(BaseModel):
    """A single mind map branch child."""
    label: str
    detail: str = ""


class MindMapBranchGroup(BaseModel):
    """A top-level mind map branch with children."""
    label: str
    children: list[MindMapBranch] = []


class MindMapData(BaseModel):
    """The mind map data structure."""
    central_topic: str
    branches: list[MindMapBranchGroup] = []


class MindMapResponse(BaseModel):
    """Mind map response."""
    id: int
    title: str
    mind_map: MindMapData
    guide_type: str = "mind_map"
    version: int = 1
    parent_guide_id: int | None = None
    created_at: datetime
    safety_checked: bool = True
    auto_created_tasks: list[AutoCreatedTask] = []

    class Config:
        from_attributes = True


class StudyGuideUpdate(BaseModel):
    """Request to update a study guide (e.g. assign/categorize to a course, rename)."""
    title: str | None = Field(default=None, max_length=200)
    course_id: int | None = None
    course_content_id: int | None = None

    @field_validator('title', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class GenerateChildRequest(BaseModel):
    """Request to generate a child sub-guide from selected text."""
    topic: str = Field(min_length=3, max_length=5000)  # The selected text
    guide_type: str = Field(default="study_guide", max_length=50)  # study_guide, quiz, flashcards, worksheet, weak_area_analysis, high_level_summary, answer_key, problem_solver
    custom_prompt: str | None = Field(default=None, max_length=2000)  # Optional focus (e.g., "make it harder")
    # §6.106: Strategy context inherited from parent
    document_type: str | None = Field(default=None, max_length=30)
    study_goal: str | None = Field(default=None, max_length=30)
    study_goal_text: str | None = Field(default=None, max_length=200)
    max_tokens: int | None = Field(default=None, ge=500, le=4000)

    @field_validator('guide_type')
    @classmethod
    def validate_guide_type(cls, v: str) -> str:
        if v not in ('study_guide', 'quiz', 'flashcards', 'worksheet', 'weak_area_analysis', 'high_level_summary', 'answer_key', 'problem_solver'):
            raise ValueError('guide_type must be study_guide, quiz, flashcards, worksheet, weak_area_analysis, high_level_summary, answer_key, or problem_solver')
        return v

    @field_validator('topic', 'custom_prompt', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class DuplicateCheckRequest(BaseModel):
    """Request to check for duplicate study guide before generation."""
    title: str | None = Field(default=None, max_length=200)
    guide_type: str = Field(max_length=50)  # study_guide, quiz, flashcards
    assignment_id: int | None = None
    course_id: int | None = None

    @field_validator('title', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class WeakAreaAnalyzeRequest(BaseModel):
    """Request to analyze weak areas from a test/exam."""
    content_id: int
    student_id: int | None = None


class StudyGuideTreeNode(BaseModel):
    """A node in the study guide tree hierarchy."""
    id: int
    title: str
    guide_type: str
    created_at: datetime
    children: list["StudyGuideTreeNode"] = []

    class Config:
        from_attributes = True


class StudyGuideTreeResponse(BaseModel):
    """Full tree hierarchy for a study guide with breadcrumb path."""
    root: StudyGuideTreeNode
    current_path: list[int]  # IDs from root to current guide


class DuplicateCheckResponse(BaseModel):
    """Response indicating whether a duplicate study guide exists."""
    exists: bool
    existing_guide: StudyGuideResponse | None = None
    message: str | None = None


# §6.114 — Study Q&A save actions
class SaveQAAsGuideRequest(BaseModel):
    """Save a Q&A response as a sub-guide."""
    content: str = Field(..., min_length=1)
    title: str = Field(default="", max_length=255)


class SaveQAAsMaterialRequest(BaseModel):
    """Save a Q&A response as a course material."""
    content: str = Field(..., min_length=1)
    title: str = Field(default="", max_length=255)


class SaveAsMaterialResponse(BaseModel):
    """Response from saving a Q&A response as course material."""
    id: int
    title: str
    course_id: int
    content_type: str

    class Config:
        from_attributes = True


class ClassifyDocumentResponse(BaseModel):
    """Response from document classification endpoint."""
    document_type: str
    confidence: float
    detected_subject: str = "other"
    subject_keywords_found: list[str] = []
    material_type_display: str = "Custom Document"
    error: bool = False


# ── Worksheet generation (#2956) ──

WORKSHEET_TEMPLATES = {
    "worksheet_general",
    "worksheet_math_word_problems",
    "worksheet_english",
    "worksheet_french",
}

WORKSHEET_DIFFICULTIES = {"below_grade", "grade_level", "above_grade"}


class WorksheetGenerateRequest(BaseModel):
    """Request to generate a worksheet."""
    content_id: int
    template_key: str = Field(default="worksheet_general", max_length=50)
    num_questions: int = Field(default=10, ge=5, le=20)
    difficulty: str = Field(default="grade_level", max_length=20)
    student_id: int | None = None

    @field_validator('template_key')
    @classmethod
    def validate_template_key(cls, v: str) -> str:
        if v not in WORKSHEET_TEMPLATES:
            raise ValueError(f"template_key must be one of: {', '.join(sorted(WORKSHEET_TEMPLATES))}")
        return v

    @field_validator('difficulty')
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        if v not in WORKSHEET_DIFFICULTIES:
            raise ValueError(f"difficulty must be one of: {', '.join(sorted(WORKSHEET_DIFFICULTIES))}")
        return v


class WorksheetResponse(BaseModel):
    """Worksheet response."""
    id: int
    user_id: int
    course_id: int | None
    course_content_id: int | None
    title: str
    content: str
    guide_type: str = "worksheet"
    template_key: str | None = None
    num_questions: int | None = None
    difficulty: str | None = None
    answer_key_markdown: str | None = None
    created_at: datetime
    auto_created_tasks: list[AutoCreatedTask] = []

    class Config:
        from_attributes = True
