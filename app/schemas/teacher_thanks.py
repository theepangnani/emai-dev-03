from pydantic import BaseModel, Field
from datetime import datetime


class TeacherThanksCreate(BaseModel):
    course_id: int | None = None
    message: str | None = Field(None, max_length=100)


class TeacherThanksResponse(BaseModel):
    id: int
    from_user_id: int
    teacher_id: int
    course_id: int | None
    message: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class TeacherThanksCount(BaseModel):
    teacher_id: int
    total_count: int
    week_count: int


class TeacherThanksStatus(BaseModel):
    thanked_today: bool
