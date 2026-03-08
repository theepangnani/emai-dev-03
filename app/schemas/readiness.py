"""Schemas for the Readiness Assessment feature."""

from datetime import datetime
from pydantic import BaseModel, Field


class ReadinessCheckCreate(BaseModel):
    """Parent request to create a readiness assessment."""
    student_id: int
    course_id: int
    topic: str | None = Field(default=None, max_length=500)


class ReadinessQuestion(BaseModel):
    """A single readiness question."""
    id: int
    type: str  # "multiple_choice", "short_answer", "application"
    question: str
    options: list[str] | None = None  # For multiple choice


class ReadinessCheckResponse(BaseModel):
    """Response after creating a readiness assessment."""
    id: int
    student_id: int
    course_id: int
    topic: str | None
    questions: list[ReadinessQuestion]
    created_at: datetime

    class Config:
        from_attributes = True


class AnswerSubmission(BaseModel):
    """A single answer from the student."""
    question_id: int
    answer: str


class ReadinessSubmitRequest(BaseModel):
    """Student submitting answers to a readiness check."""
    answers: list[AnswerSubmission]


class TopicBreakdown(BaseModel):
    """Score breakdown for a single topic area."""
    topic: str
    score: int  # 1-5
    status: str  # "strong", "developing", "needs_work"
    feedback: str


class ReadinessReportResponse(BaseModel):
    """Gap analysis report for the parent."""
    id: int
    student_id: int
    student_name: str
    course_name: str
    topic: str | None
    overall_score: int  # 1-5
    summary: str
    topic_breakdown: list[TopicBreakdown]
    suggestions: list[str]
    questions: list[ReadinessQuestion]
    answers: list[AnswerSubmission] | None = None
    created_at: datetime
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class ReadinessListItem(BaseModel):
    """Summary item for listing readiness checks."""
    id: int
    student_name: str
    course_name: str
    topic: str | None
    overall_score: int | None
    status: str  # "pending", "completed"
    created_at: datetime

    class Config:
        from_attributes = True
