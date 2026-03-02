"""Pydantic schemas for Writing Assistance API."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.models.writing_assistance import WritingFeedbackType


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class WritingAnalysisRequest(BaseModel):
    """Request body for analyzing a piece of writing."""

    title: str
    text: str
    course_id: Optional[int] = None
    assignment_type: Optional[str] = "essay"  # essay | report | letter | lab


class WritingImproveRequest(BaseModel):
    """Request body for applying a specific improvement instruction to a session."""

    session_id: int
    instruction: str  # e.g. "make it more formal", "add more evidence"


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class WritingFeedbackItem(BaseModel):
    """A single feedback item returned by the AI."""

    type: WritingFeedbackType
    message: str
    suggestion: str
    severity: Literal["info", "warning", "error"]


class WritingAnalysisResponse(BaseModel):
    """Response returned after analyzing a piece of writing."""

    session_id: int
    overall_score: int
    feedback: list[WritingFeedbackItem]
    improved_text: str
    suggestions_count: int
    word_count: int


class WritingImproveResponse(BaseModel):
    """Response returned after applying an improvement instruction."""

    improved_text: str
    instruction: str


class WritingSessionSummary(BaseModel):
    """Summary of a writing session (no full text) for list views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    assignment_type: str
    overall_score: Optional[int]
    word_count: int
    suggestions_count: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime]


class WritingSessionDetail(BaseModel):
    """Full writing session including original and improved text."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    assignment_type: str
    original_text: str
    improved_text: Optional[str]
    feedback: Optional[list[WritingFeedbackItem]]
    overall_score: Optional[int]
    word_count: int
    course_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]


class WritingTemplateResponse(BaseModel):
    """Response schema for a writing template."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    template_type: str
    structure_outline: str
    is_active: bool
