from pydantic import BaseModel
from datetime import datetime


class AssignmentCreate(BaseModel):
    title: str
    description: str | None = None
    course_id: int
    due_date: datetime | None = None
    max_points: float | None = None


class AssignmentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: datetime | None = None
    max_points: float | None = None


class AssignmentResponse(BaseModel):
    id: int
    title: str
    description: str | None
    course_id: int
    course_name: str | None = None
    google_classroom_id: str | None
    due_date: datetime | None
    max_points: float | None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Submission schemas (#839) ──────────────────────────────

class SubmissionResponse(BaseModel):
    """Response for a student's assignment submission."""
    id: int
    student_id: int
    assignment_id: int
    status: str
    submitted_at: datetime | None = None
    grade: float | None = None
    submission_file_name: str | None = None
    submission_notes: str | None = None
    is_late: bool = False
    assignment_title: str | None = None
    course_name: str | None = None
    student_name: str | None = None
    has_file: bool = False

    class Config:
        from_attributes = True


class SubmissionListItem(BaseModel):
    """Summary of a submission for teacher's list view."""
    student_id: int
    student_name: str
    status: str
    submitted_at: datetime | None = None
    is_late: bool = False
    grade: float | None = None
    has_file: bool = False

    class Config:
        from_attributes = True
