from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CourseCreate(BaseModel):
    name: str
    description: str | None = None
    subject: str | None = None
    teacher_id: int | None = None
    teacher_email: str | None = None


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    teacher_email: Optional[str] = None


class CourseResponse(BaseModel):
    id: int
    name: str
    description: str | None
    subject: str | None
    google_classroom_id: str | None
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


class AddStudentRequest(BaseModel):
    email: str
