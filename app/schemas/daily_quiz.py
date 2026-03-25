from datetime import date, datetime

from pydantic import BaseModel


class DailyQuizQuestion(BaseModel):
    question: str
    options: dict[str, str]
    correct_answer: str
    explanation: str


class DailyQuizResponse(BaseModel):
    id: int
    user_id: int
    quiz_date: date
    questions: list[DailyQuizQuestion]
    total_questions: int
    score: int | None
    percentage: float | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


class DailyQuizSubmit(BaseModel):
    answers: dict[int, str]  # question_index -> selected_answer


class DailyQuizSubmitResponse(BaseModel):
    score: int
    total_questions: int
    percentage: float
    xp_awarded: int | None = None
