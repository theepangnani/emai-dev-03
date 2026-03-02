"""
Pydantic schemas for the Learning Journal feature.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.learning_journal import JournalMood


# ---------------------------------------------------------------------------
# Journal Entry
# ---------------------------------------------------------------------------

class JournalEntryCreate(BaseModel):
    title: Optional[str] = None
    content: str = Field(..., min_length=1)
    mood: Optional[JournalMood] = None
    tags: Optional[list[str]] = None
    course_id: Optional[int] = None
    ai_prompt_used: Optional[str] = None
    is_teacher_visible: bool = False


class JournalEntryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    mood: Optional[JournalMood] = None
    tags: Optional[list[str]] = None
    course_id: Optional[int] = None
    is_teacher_visible: Optional[bool] = None


class JournalEntryResponse(BaseModel):
    id: int
    student_id: int
    course_id: Optional[int] = None
    title: Optional[str] = None
    content: str
    mood: Optional[JournalMood] = None
    tags: Optional[list[str]] = None
    ai_prompt_used: Optional[str] = None
    is_teacher_visible: bool
    word_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class JournalStats(BaseModel):
    total_entries: int
    avg_words: float
    mood_distribution: dict[str, int]  # mood_value -> count
    streak_days: int
    entries_this_week: int


# ---------------------------------------------------------------------------
# Reflection Prompt
# ---------------------------------------------------------------------------

class ReflectionPromptResponse(BaseModel):
    id: Optional[int] = None  # None when AI-generated on the fly
    prompt_text: str
    category: str
    is_ai_generated: bool = False

    model_config = {"from_attributes": True}
