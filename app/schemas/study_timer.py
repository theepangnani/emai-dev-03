from __future__ import annotations

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel

from app.models.study_timer import SessionType


class StudySessionCreate(BaseModel):
    session_type: SessionType = SessionType.WORK
    course_id: Optional[int] = None


class StudySessionEnd(BaseModel):
    pass  # No extra payload needed — server calculates duration from started_at


class StudySessionResponse(BaseModel):
    id: int
    user_id: int
    session_type: SessionType
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    course_id: Optional[int] = None
    completed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StudyStreakResponse(BaseModel):
    id: int
    user_id: int
    current_streak: int
    longest_streak: int
    last_session_date: Optional[date] = None
    total_sessions: int
    total_focus_minutes: int

    model_config = {"from_attributes": True}


class DayStats(BaseModel):
    date: str  # ISO date string YYYY-MM-DD
    minutes: int


class StudyStatsResponse(BaseModel):
    today_minutes: int
    week_minutes: int
    total_sessions: int
    current_streak: int
    longest_streak: int
    sessions_by_day: List[DayStats]
