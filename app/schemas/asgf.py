"""Pydantic schemas for the AI Study Guide Factory (ASGF)."""
from pydantic import BaseModel, Field


class IntentClassifyRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class IntentClassifyResponse(BaseModel):
    subject: str = ""
    grade_level: str = ""
    topic: str = ""
    confidence: float = 0.0
    bloom_tier: str = ""
