"""Schemas for the Weekly Progress Pulse digest."""

from pydantic import BaseModel


class DigestChildTask(BaseModel):
    completed: int = 0
    total: int = 0


class DigestChildAssignment(BaseModel):
    submitted: int = 0
    due: int = 0


class DigestQuizScore(BaseModel):
    quiz_count: int = 0
    average_percentage: float | None = None


class DigestOverdueItem(BaseModel):
    id: int
    title: str
    due_date: str | None = None
    item_type: str  # "task" or "assignment"


class ChildDigest(BaseModel):
    student_id: int
    full_name: str
    grade_level: int | None = None
    tasks: DigestChildTask = DigestChildTask()
    assignments: DigestChildAssignment = DigestChildAssignment()
    study_guides_created: int = 0
    quiz_scores: DigestQuizScore = DigestQuizScore()
    overdue_items: list[DigestOverdueItem] = []
    highlight: str = ""  # one-line summary


class WeeklyDigestResponse(BaseModel):
    """JSON preview of the weekly digest for a parent."""
    week_start: str  # ISO date
    week_end: str  # ISO date
    greeting: str
    children: list[ChildDigest] = []
    overall_summary: str = ""


class WeeklyDigestSendResponse(BaseModel):
    success: bool
    message: str
