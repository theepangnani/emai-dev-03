from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.schemas.course import CourseResponse
from app.schemas.assignment import AssignmentResponse


class CreateChildRequest(BaseModel):
    full_name: str
    email: str | None = None
    relationship_type: str = "guardian"


class LinkChildRequest(BaseModel):
    student_email: str
    full_name: str | None = None
    relationship_type: str = "guardian"


class ChildSummary(BaseModel):
    student_id: int
    user_id: int
    full_name: str
    grade_level: Optional[int]
    school_name: Optional[str]
    relationship_type: str | None = None
    invite_link: str | None = None

    class Config:
        from_attributes = True


class DiscoveredChild(BaseModel):
    user_id: int
    email: str
    full_name: str
    google_courses: list[str]
    already_linked: bool


class DiscoverChildrenResponse(BaseModel):
    discovered: list[DiscoveredChild]
    google_connected: bool
    courses_searched: int


class LinkChildrenBulkRequest(BaseModel):
    user_ids: list[int]
    relationship_type: str = "guardian"


class CourseWithTeacher(CourseResponse):
    teacher_name: str | None = None
    teacher_email: str | None = None


class ChildUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    grade_level: Optional[int] = None
    school_name: Optional[str] = None


class ChildOverview(BaseModel):
    student_id: int
    user_id: int
    full_name: str
    grade_level: Optional[int]
    google_connected: bool = False
    courses: list[CourseWithTeacher]
    assignments: list[AssignmentResponse]
    study_guides_count: int


class ChildHighlight(BaseModel):
    """Per-child summary for the parent dashboard status view."""
    student_id: int
    user_id: int
    full_name: str
    grade_level: Optional[int] = None
    overdue_count: int = 0
    due_today_count: int = 0
    upcoming_count: int = 0
    completed_today_count: int = 0
    courses: list[CourseWithTeacher] = []
    overdue_items: list[dict] = []
    due_today_items: list[dict] = []


class ParentDashboardResponse(BaseModel):
    """Aggregated dashboard data returned in a single API call."""
    children: list[ChildSummary]
    google_connected: bool = False
    unread_messages: int = 0
    total_overdue: int = 0
    total_due_today: int = 0
    total_tasks: int = 0
    child_highlights: list[ChildHighlight] = []
    all_assignments: list[AssignmentResponse] = []
    all_tasks: list[dict] = []
