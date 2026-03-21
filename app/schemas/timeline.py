"""Pydantic schemas for the Study Timeline feature (#2017)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TimelineEntry(BaseModel):
    """Single timeline activity entry."""
    type: str  # upload, study_guide, quiz, badge, level_up
    title: str
    course: Optional[str] = None
    date: str  # ISO date string
    xp: Optional[int] = None
    score: Optional[int] = None
    badge_id: Optional[str] = None


class TimelineResponse(BaseModel):
    """Paginated timeline response."""
    items: list[TimelineEntry] = Field(default_factory=list)
    total: int = 0
