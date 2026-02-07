from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.schemas.course import CourseResponse
from app.schemas.assignment import AssignmentResponse


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


class ChildOverview(BaseModel):
    student_id: int
    user_id: int
    full_name: str
    grade_level: Optional[int]
    google_connected: bool = False
    courses: list[CourseWithTeacher]
    assignments: list[AssignmentResponse]
    study_guides_count: int
