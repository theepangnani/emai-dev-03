from pydantic import BaseModel
from typing import Optional


class JourneyHintResponse(BaseModel):
    hint_key: str
    title: str
    description: str
    journey_id: str
    journey_url: str
    diagram_url: str


class JourneyHintResult(BaseModel):
    hint: Optional[JourneyHintResponse] = None


class JourneyHintAction(BaseModel):
    success: bool
    message: str
