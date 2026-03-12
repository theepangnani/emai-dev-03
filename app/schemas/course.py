from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

from app.schemas.user import strip_whitespace


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    subject: str | None = Field(default=None, max_length=100)
    teacher_id: int | None = None
    teacher_email: str | None = Field(default=None, max_length=255)
    student_ids: list[int] = Field(default_factory=list)
    require_approval: bool = False
    # Inline teacher creation fields
    new_teacher_name: str | None = Field(default=None, max_length=255)
    new_teacher_email: str | None = Field(default=None, max_length=255)

    @field_validator('name', 'description', 'subject', 'teacher_email', 'new_teacher_name', 'new_teacher_email', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class CourseUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    subject: Optional[str] = Field(default=None, max_length=100)
    teacher_id: Optional[int] = None
    teacher_email: Optional[str] = Field(default=None, max_length=255)
    require_approval: Optional[bool] = None

    @field_validator('name', 'description', 'subject', 'teacher_email', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class CourseResponse(BaseModel):
    id: int
    name: str
    description: str | None
    subject: str | None
    google_classroom_id: str | None
    class_code: str | None = None
    classroom_type: str | None = "manual"
    teacher_id: int | None
    teacher_name: str | None = None
    teacher_email: str | None = None
    created_by_user_id: int | None = None
    is_private: bool = False
    is_default: bool = False
    require_approval: bool = False
    student_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class TeacherCourseManagementResponse(BaseModel):
    """Enriched course data for teacher course management view (#947)."""
    id: int
    name: str
    description: str | None
    subject: str | None
    google_classroom_id: str | None
    class_code: str | None = None
    classroom_type: str | None = "manual"
    teacher_id: int | None
    teacher_name: str | None = None
    created_by_user_id: int | None = None
    is_private: bool = False
    is_default: bool = False
    student_count: int = 0
    assignment_count: int = 0
    material_count: int = 0
    last_activity: datetime | None = None
    source: str = "manual"  # "google", "manual", or "admin"
    created_at: datetime

    class Config:
        from_attributes = True


class EnrollmentRequestResponse(BaseModel):
    id: int
    course_id: int
    student_id: int
    requested_by_user_id: int | None = None
    status: str
    student_name: str | None = None
    student_email: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by_user_id: int | None = None

    class Config:
        from_attributes = True


class EnrollmentRequestUpdate(BaseModel):
    status: str  # "approved" or "rejected"


class AddStudentRequest(BaseModel):
    email: str = Field(max_length=255)
    message: str | None = Field(default=None, max_length=500)  # Optional message to include in the invite (#551)

    @field_validator('email', 'message', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)
