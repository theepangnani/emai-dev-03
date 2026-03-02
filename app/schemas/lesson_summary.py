from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.models.lesson_summary import InputType


# ---------------------------------------------------------------------------
# Nested sub-schemas
# ---------------------------------------------------------------------------

class KeyConcept(BaseModel):
    concept: str
    definition: str


class ImportantDate(BaseModel):
    date: str
    event: str


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class LessonSummaryRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Summary title")
    raw_input: str = Field(..., min_length=10, description="Raw class notes / transcript text")
    input_type: InputType = Field(InputType.TEXT, description="Input content type")
    course_id: Optional[int] = Field(None, description="Optional course association")


class LessonSummaryUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    raw_input: Optional[str] = Field(None, min_length=10)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class LessonSummaryListItem(BaseModel):
    id: int
    title: str
    course_id: Optional[int]
    course_name: Optional[str]
    input_type: InputType
    word_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class LessonSummaryResponse(BaseModel):
    id: int
    student_id: int
    course_id: Optional[int]
    course_name: Optional[str]
    title: str
    input_type: InputType
    raw_input: str
    summary: Optional[str]
    key_concepts: Optional[List[KeyConcept]]
    important_dates: Optional[List[ImportantDate]]
    study_questions: Optional[List[str]]
    action_items: Optional[List[str]]
    word_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class FlashcardsFromSummaryResponse(BaseModel):
    """Response when converting key concepts to flashcards."""
    study_guide_id: int
    title: str
    card_count: int
    message: str
