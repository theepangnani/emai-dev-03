"""
XP Gamification schemas — Pydantic models for the XP system.

Part of the Gamification System (#2000).
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class XpSummaryResponse(BaseModel):
    total_xp: int
    current_level: int
    level_title: str
    current_streak: int
    longest_streak: int
    freeze_tokens_remaining: int
    xp_to_next_level: int
    today_xp: int
    today_cap: int

    class Config:
        from_attributes = True


class XpLedgerEntry(BaseModel):
    action_type: str
    xp_awarded: int
    multiplier: float
    awarder_name: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class XpHistoryResponse(BaseModel):
    entries: list[XpLedgerEntry]
    total_count: int


class BadgeResponse(BaseModel):
    badge_id: str
    badge_name: str
    badge_description: str
    awarded_at: Optional[datetime] = None
    earned: bool
