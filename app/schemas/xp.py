"""Pydantic schemas for the XP / Gamification system."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class XpSummaryResponse(BaseModel):
    """Current user's XP summary."""
    user_id: int = 0
    total_xp: int = 0
    level: int = 1
    current_level: int = 1
    level_title: str = "Curious Learner"
    current_streak: int = 0
    longest_streak: int = 0
    freeze_tokens_remaining: int = 1
    xp_to_next_level: int = 200
    today_xp: int = 0
    today_cap: int = 0

    model_config = ConfigDict(from_attributes=True)


class XpLedgerEntry(BaseModel):
    """Single XP ledger row."""
    action_type: str
    xp_awarded: int
    multiplier: float = 1.0
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class XpHistoryResponse(BaseModel):
    """Paginated XP history."""
    items: list[XpLedgerEntry] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0

    @property
    def entries(self) -> list[XpLedgerEntry]:
        """Alias for items (backward compat with service-layer tests)."""
        return self.items

    @property
    def total_count(self) -> int:
        """Alias for total (backward compat with service-layer tests)."""
        return self.total


class BadgeResponse(BaseModel):
    """Badge info (earned or unearned)."""
    badge_id: str
    badge_name: str
    badge_description: str
    earned: bool = False
    awarded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class StreakResponse(BaseModel):
    """Current streak info."""
    current_streak: int = 0
    longest_streak: int = 0
    freeze_tokens_remaining: int = 1
    multiplier: float = 1.0
    tier: str = "grey"
    streak_tier: Optional[str] = None
    tier_label: Optional[str] = None
    last_streak_date: Optional[str] = None
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
