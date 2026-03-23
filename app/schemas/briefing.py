"""Schemas for the Daily Briefing endpoint."""

from datetime import datetime
from pydantic import BaseModel


class BriefingTask(BaseModel):
    id: int
    title: str
    due_date: datetime | None = None
    priority: str = "medium"
    course_name: str | None = None
    is_overdue: bool = False


class BriefingAssignment(BaseModel):
    id: int
    title: str
    due_date: datetime | None = None
    course_name: str
    max_points: float | None = None
    status: str = "pending"  # pending, submitted, graded
    is_late: bool = False


class ChildBriefing(BaseModel):
    student_id: int
    full_name: str
    grade_level: int | None = None
    overdue_tasks: list[BriefingTask] = []
    due_today_tasks: list[BriefingTask] = []
    upcoming_assignments: list[BriefingAssignment] = []
    recent_study_count: int = 0  # study guides created in last 7 days
    needs_attention: bool = False  # True if overdue items exist


class DailyBriefingResponse(BaseModel):
    """Single-call response for the parent Daily Briefing card."""
    date: str  # ISO date string
    greeting: str  # e.g. "Good morning, Sarah"
    children: list[ChildBriefing] = []
    total_overdue: int = 0
    total_due_today: int = 0
    total_upcoming: int = 0
    attention_needed: bool = False  # True if any child needs attention


class HelpMyKidRequest(BaseModel):
    """Request to generate a study guide for a parent's child."""
    student_id: int
    item_type: str  # "task" or "assignment"
    item_id: int


class HelpMyKidResponse(BaseModel):
    """Response after generating a study guide via Help My Kid."""
    study_guide_id: int
    title: str
    safety_checked: bool = True
