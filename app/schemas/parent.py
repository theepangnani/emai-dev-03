from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import date, datetime
from typing import Optional

from app.schemas.course import CourseResponse
from app.schemas.assignment import AssignmentResponse
from app.schemas.user import strip_whitespace


class CreateChildRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    relationship_type: str = Field(default="guardian", max_length=50)

    @field_validator('full_name', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class LinkChildRequest(BaseModel):
    student_email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    relationship_type: str = Field(default="guardian", max_length=50)

    @field_validator('full_name', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class ChildSummary(BaseModel):
    student_id: int
    user_id: int
    full_name: str
    email: Optional[str] = None
    grade_level: Optional[int]
    school_name: Optional[str]
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    postal_code: Optional[str] = None
    notes: Optional[str] = None
    interests: list[str] = []
    relationship_type: str | None = None
    invite_link: str | None = None
    link_request_pending: bool = False
    course_count: int = 0
    active_task_count: int = 0
    invite_status: str | None = None  # "active", "pending", or "email_unverified"
    invite_id: int | None = None  # ID of pending invite (for resend)

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
    relationship_type: str = Field(default="guardian", max_length=50)


class CourseWithTeacher(CourseResponse):
    teacher_name: str | None = None
    teacher_email: str | None = None


class ChildUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=255)
    email: Optional[EmailStr] = None
    grade_level: Optional[int] = None
    school_name: Optional[str] = Field(default=None, max_length=200)
    date_of_birth: Optional[date] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    address: Optional[str] = Field(default=None, max_length=500)
    city: Optional[str] = Field(default=None, max_length=100)
    province: Optional[str] = Field(default=None, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=2000)
    interests: Optional[list[str]] = None

    @field_validator('interests', mode='before')
    @classmethod
    def validate_interests(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        if len(v) > 10:
            raise ValueError("Maximum 10 interests allowed")
        cleaned = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError("Each interest must be a string")
            stripped = item.strip().lower()
            if not stripped:
                continue
            if len(stripped) > 50:
                raise ValueError("Each interest must be 50 characters or less")
            cleaned.append(stripped)
        return cleaned

    @field_validator('full_name', 'school_name', 'address', 'city', 'province', 'notes', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


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


class ChildResetPasswordRequest(BaseModel):
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


class LinkTeacherRequest(BaseModel):
    teacher_email: EmailStr
    teacher_name: str | None = Field(default=None, max_length=255)

    @field_validator('teacher_name', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class LinkedTeacher(BaseModel):
    id: int
    student_id: int
    teacher_user_id: int | None = None
    teacher_name: str | None = None
    teacher_email: str | None = None
    added_by_user_id: int
    created_at: datetime | None = None

    class Config:
        from_attributes = True


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
