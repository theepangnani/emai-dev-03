from pydantic import BaseModel
from datetime import datetime


class AssignmentCreate(BaseModel):
    title: str
    description: str | None = None
    course_id: int
    due_date: datetime | None = None
    max_points: float | None = None


class AssignmentResponse(BaseModel):
    id: int
    title: str
    description: str | None
    course_id: int
    google_classroom_id: str | None
    due_date: datetime | None
    max_points: float | None
    created_at: datetime

    class Config:
        from_attributes = True
