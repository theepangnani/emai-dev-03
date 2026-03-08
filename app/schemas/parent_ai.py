"""Schemas for Responsible AI Parent Tools."""
from pydantic import BaseModel, Field
from typing import Optional


# ── Requests ──

class WeakSpotsRequest(BaseModel):
    student_id: int
    course_id: int | None = None


class ReadinessCheckRequest(BaseModel):
    student_id: int
    assignment_id: int


class PracticeProblemsRequest(BaseModel):
    student_id: int
    course_id: int
    topic: str = Field(min_length=1, max_length=500)


# ── Responses ──

class WeakSpot(BaseModel):
    topic: str
    severity: str  # "high", "medium", "low"
    detail: str
    quiz_score_summary: str | None = None
    suggested_action: str


class WeakSpotsResponse(BaseModel):
    student_name: str
    course_name: str | None = None
    weak_spots: list[WeakSpot]
    summary: str
    total_quizzes_analyzed: int = 0
    total_assignments_analyzed: int = 0


class ReadinessItem(BaseModel):
    label: str
    status: str  # "done", "partial", "missing"
    detail: str | None = None


class ReadinessCheckResponse(BaseModel):
    student_name: str
    assignment_title: str
    course_name: str
    readiness_score: int = Field(ge=1, le=5)
    summary: str
    items: list[ReadinessItem]


class PracticeProblem(BaseModel):
    number: int
    question: str
    hint: str | None = None


class PracticeProblemsResponse(BaseModel):
    student_name: str
    course_name: str
    topic: str
    problems: list[PracticeProblem]
    instructions: str
