"""Pydantic schemas for journey hints (#2604, #2609)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class JourneyHintBase(BaseModel):
    hint_key: str
    status: str = "shown"
    engaged: Optional[bool] = None


class JourneyHintCreate(JourneyHintBase):
    pass


class JourneyHintResponse(JourneyHintBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class JourneyHintEngagement(BaseModel):
    """Payload for recording whether the user engaged with a hint."""
    hint_key: str
    engaged: bool
