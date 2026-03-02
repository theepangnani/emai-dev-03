"""Pydantic schemas for gamification endpoints."""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel

from app.models.gamification import BadgeCategory


class BadgeDefinitionResponse(BaseModel):
    id: int
    key: str
    name: str
    description: str
    icon_emoji: str
    category: BadgeCategory
    xp_reward: int
    criteria_json: Optional[Any] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserBadgeResponse(BaseModel):
    id: int
    user_id: int
    badge_id: int
    earned_at: datetime
    notified: bool
    badge: BadgeDefinitionResponse

    model_config = {"from_attributes": True}


class UserXPResponse(BaseModel):
    id: int
    user_id: int
    total_xp: int
    level: int
    xp_this_week: int
    leaderboard_opt_in: bool
    updated_at: Optional[datetime] = None
    # Computed helpers
    xp_for_next_level: int
    xp_progress: int  # XP accumulated towards next level threshold

    model_config = {"from_attributes": True}


class XPTransactionResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    rank: int
    display_name: str  # truncated / anonymised
    level: int
    total_xp: int
    badge_count: int

    model_config = {"from_attributes": True}


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry]
    total: int


class LeaderboardOptInRequest(BaseModel):
    opt_in: bool


class NewBadgeNotification(BaseModel):
    """Returned alongside XP/badge data so the frontend can show toasts."""
    badge: BadgeDefinitionResponse
    xp_awarded: int
