"""Pydantic schemas for CB-TUTOR-002 Phase 2 Learning Cycle (#4067)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- Session ---

class LearningCycleSessionCreate(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)
    subject: str = Field(..., min_length=1, max_length=100)
    grade_level: int | None = None


class LearningCycleSessionResponse(BaseModel):
    id: str
    user_id: int
    topic: str
    subject: str
    grade_level: int | None
    status: str
    current_chunk_idx: int
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


# --- Chunk ---

class LearningCycleChunkCreate(BaseModel):
    order_index: int = Field(..., ge=0)
    teach_content_md: str = Field(..., min_length=1)


class LearningCycleChunkResponse(BaseModel):
    id: str
    session_id: str
    order_index: int
    teach_content_md: str
    mastery_status: str

    class Config:
        from_attributes = True


# --- Question ---

class LearningCycleQuestionCreate(BaseModel):
    order_index: int = Field(..., ge=0)
    format: str = Field(..., pattern="^(mcq|true_false|fill_blank)$")
    prompt: str = Field(..., min_length=1)
    options: dict[str, Any] | list[Any] | None = None
    correct_answer: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)


class LearningCycleQuestionResponse(BaseModel):
    id: str
    chunk_id: str
    order_index: int
    format: str
    prompt: str
    options: Any | None
    correct_answer: str
    explanation: str

    class Config:
        from_attributes = True


# --- Answer ---

class LearningCycleAnswerCreate(BaseModel):
    attempt_number: int = Field(default=1, ge=1)
    answer_given: str
    is_correct: bool = False
    xp_awarded: int = Field(default=0, ge=0)


class LearningCycleAnswerResponse(BaseModel):
    id: str
    question_id: str
    attempt_number: int
    answer_given: str
    is_correct: bool
    xp_awarded: int
    created_at: datetime

    class Config:
        from_attributes = True
