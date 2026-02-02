from pydantic import BaseModel
from datetime import datetime


class StudyGuideCreate(BaseModel):
    """Request to generate a study guide."""
    assignment_id: int | None = None
    course_id: int | None = None
    title: str | None = None  # Optional custom title
    content: str | None = None  # Optional custom content to base guide on


class StudyGuideResponse(BaseModel):
    """Study guide response."""
    id: int
    user_id: int
    assignment_id: int | None
    course_id: int | None
    title: str
    content: str
    guide_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class QuizGenerateRequest(BaseModel):
    """Request to generate a quiz."""
    assignment_id: int | None = None
    course_id: int | None = None
    topic: str | None = None
    content: str | None = None
    num_questions: int = 5


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
    created_at: datetime

    class Config:
        from_attributes = True


class FlashcardGenerateRequest(BaseModel):
    """Request to generate flashcards."""
    assignment_id: int | None = None
    course_id: int | None = None
    topic: str | None = None
    content: str | None = None
    num_cards: int = 10


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
    created_at: datetime

    class Config:
        from_attributes = True
