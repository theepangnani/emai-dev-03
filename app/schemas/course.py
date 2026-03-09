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
    teacher_email: Optional[str] = Field(default=None, max_length=255)

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
    classroom_type: str | None = "manual"
    teacher_id: int | None
    teacher_name: str | None = None
    teacher_email: str | None = None
    created_by_user_id: int | None = None
    is_private: bool = False
    is_default: bool = False
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


class AddStudentRequest(BaseModel):
    email: str = Field(max_length=255)
    message: str | None = Field(default=None, max_length=500)  # Optional message to include in the invite (#551)

    @field_validator('email', 'message', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)
