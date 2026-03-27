"""Pydantic schemas for Quiz of the Day."""
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.study import QuizQuestion


class DailyQuizResponse(BaseModel):
    """Response for GET /quiz-of-the-day."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    quiz_date: date
    title: str
    questions: list[QuizQuestion]
    score: int | None = None
    total_questions: int = 5
    completed_at: datetime | None = None
    xp_awarded: int | None = None
    course_name: str | None = None


class DailyQuizCompleteRequest(BaseModel):
    """Request body for POST /quiz-of-the-day/complete."""
    answers: dict[int, str] = Field(
        ...,
        description="Map of question index (0-based) to selected answer letter (A/B/C/D)",
    )


class DailyQuizCompleteResponse(BaseModel):
    """Response for POST /quiz-of-the-day/complete."""
    score: int
    total_questions: int
    xp_awarded: int
    results: list[dict]  # Per-question result with correct/incorrect and explanation
