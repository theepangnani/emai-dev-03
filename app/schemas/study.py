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
    focus_prompt: str | None = None
    created_at: datetime
    archived_at: datetime | None = None
    auto_created_tasks: list[AutoCreatedTask] = []

    # Sharing fields
    shared_with_user_id: int | None = None
    shared_at: datetime | None = None
    viewed_at: datetime | None = None
    viewed_count: int = 0
    shared_with_name: str | None = None

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
    version: int = 1
    parent_guide_id: int | None = None
    created_at: datetime
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
    version: int = 1
    parent_guide_id: int | None = None
    created_at: datetime
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


class DuplicateCheckResponse(BaseModel):
    """Response indicating whether a duplicate study guide exists."""
    exists: bool
    existing_guide: StudyGuideResponse | None = None
    message: str | None = None
