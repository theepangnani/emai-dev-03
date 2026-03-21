"""Pydantic schemas for the XP / Gamification system."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class XpSummaryResponse(BaseModel):
    """Current user's XP summary."""
    user_id: int
    total_xp: int = 0
    level: int = 1
    current_level_xp: int = 0
    next_level_xp: int = 100
    streak_days: int = 0
    longest_streak: int = 0

    model_config = ConfigDict(from_attributes=True)


class XpLedgerEntry(BaseModel):
    """Single XP ledger row."""
    id: int
    user_id: int
    xp_amount: int
    action: str
    description: Optional[str] = None
    awarder_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class XpHistoryResponse(BaseModel):
    """Paginated XP history."""
    items: list[XpLedgerEntry]
    total: int
    limit: int
    offset: int


class BadgeResponse(BaseModel):
    """Badge info (earned or unearned)."""
    id: int
    slug: str
    name: str
    description: str
    icon: Optional[str] = None
    earned: bool = False
    earned_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class StreakResponse(BaseModel):
    """Current streak info."""
    current_streak: int = 0
    longest_streak: int = 0
    last_activity_date: Optional[str] = None


class BrowniePointRequest(BaseModel):
    """Parent/Teacher awards brownie points to a student."""
    student_user_id: int
    points: int = Field(ge=1, le=50, description="Points to award (1-50)")
    reason: Optional[str] = Field(None, max_length=200)


class BrowniePointResponse(BaseModel):
    """Response after awarding brownie points."""
    awarded: int
    student_user_id: int
    new_total_xp: int
    message: str
