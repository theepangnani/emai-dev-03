"""Pydantic schemas for DetectedEvent."""
from datetime import date, datetime
from pydantic import BaseModel, Field


class DetectedEventCreate(BaseModel):
    event_type: str = Field(..., max_length=30)
    event_title: str = Field(..., max_length=200)
    event_date: date
    course_id: int | None = None
    source: str = Field(default="manual", max_length=30)


class DetectedEventResponse(BaseModel):
    id: int
    student_id: int
    course_id: int | None = None
    course_content_id: int | None = None
    event_type: str
    event_title: str
    event_date: date
    source: str
    dismissed: bool
    created_at: datetime | None = None
    days_remaining: int | None = None

    model_config = {"from_attributes": True}
