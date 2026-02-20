from pydantic import BaseModel
from datetime import datetime


class QuizResultCreate(BaseModel):
    study_guide_id: int
    score: int
    total_questions: int
    answers: dict[int, str]
    time_taken_seconds: int | None = None


class QuizResultResponse(BaseModel):
    id: int
    user_id: int
    study_guide_id: int
    score: int
    total_questions: int
    percentage: float
    answers_json: str
    attempt_number: int
    time_taken_seconds: int | None
    completed_at: datetime
    quiz_title: str | None = None

    class Config:
        from_attributes = True


class QuizResultSummary(BaseModel):
    id: int
    study_guide_id: int
    quiz_title: str | None = None
    score: int
    total_questions: int
    percentage: float
    attempt_number: int
    completed_at: datetime

    class Config:
        from_attributes = True


class QuizHistoryStats(BaseModel):
    total_attempts: int
    unique_quizzes: int
    average_score: float
    best_score: float
    recent_trend: str  # "improving", "declining", "stable"
