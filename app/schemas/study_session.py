"""Pydantic schemas for Study Sessions (Pomodoro) (#2021)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class StudySessionStart(BaseModel):
    """Request body to start a study session."""
    course_id: Optional[int] = None
    subject: Optional[str] = None
    target_duration: int = 1500  # 25 min default


class StudySessionComplete(BaseModel):
    """Request body to complete a study session."""
    duration_seconds: int


class StudySessionResponse(BaseModel):
    """Single study session response."""
    id: int
    student_id: int
    course_id: Optional[int] = None
    subject: Optional[str] = None
    duration_seconds: int
    target_duration: int = 1500
    completed: bool = False
    ai_recap: Optional[str] = None
    xp_awarded: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StudySessionListResponse(BaseModel):
    """Paginated list of study sessions."""
    items: list[StudySessionResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


class StudySessionStats(BaseModel):
    """Weekly study session stats."""
    total_sessions: int = 0
    total_minutes: int = 0
    xp_earned: int = 0
