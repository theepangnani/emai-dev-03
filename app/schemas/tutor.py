"""Pydantic schemas for the Tutor Chat endpoint — CB-TUTOR-002 Phase 1 (#4063)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TutorChatContextOverride(BaseModel):
    """Optional caller-supplied context (child, grade, subject, course)."""

    child_id: int | None = None
    grade_level: int | None = None
    subject: str | None = None
    course_id: int | None = None


class TutorChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    context_override: TutorChatContextOverride | None = None


class TutorChatDoneResponse(BaseModel):
    """Payload emitted on the terminal `event: done` SSE frame."""

    conversation_id: str
    message_id: str
    credits_used: float
