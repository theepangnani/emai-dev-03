"""Schemas for parent-initiated study requests."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class StudyRequestCreate(BaseModel):
    student_id: int
    subject: str = Field(..., min_length=1, max_length=100)
    topic: Optional[str] = Field(None, max_length=200)
    urgency: Literal["low", "normal", "high"] = "normal"
    message: Optional[str] = Field(None, max_length=500)


class StudyRequestResponse(BaseModel):
    id: int
    parent_id: int
    student_id: int
    subject: str
    topic: Optional[str] = None
    urgency: str
    message: Optional[str] = None
    status: str
    student_response: Optional[str] = None
    responded_at: Optional[datetime] = None
    created_at: datetime
    parent_name: Optional[str] = None

    model_config = {"from_attributes": True}


class StudyRequestRespond(BaseModel):
    status: Literal["accepted", "deferred", "completed"]
    response: Optional[str] = Field(None, max_length=500)


class StudyRequestPendingCount(BaseModel):
    count: int
