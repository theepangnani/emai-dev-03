"""Pydantic schemas for journey hints."""

from typing import Optional

from pydantic import BaseModel


class JourneyHintResponse(BaseModel):
    """Single hint returned by GET /api/journey/hints."""
    hint_key: str
    title: str
    description: str
    journey_id: str
    journey_url: str
    diagram_url: str


class JourneyHintResult(BaseModel):
    """Wrapper — hint is None when no hint applies."""
    hint: Optional[JourneyHintResponse] = None


class JourneyHintAction(BaseModel):
    """Response for dismiss/snooze/suppress-all actions."""
    success: bool
    message: str


class JourneyHintEngagement(BaseModel):
    """Payload for recording whether the user engaged with a hint."""
    hint_key: str
    engaged: bool
