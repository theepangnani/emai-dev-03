from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.homework_help import HelpMode, SubjectArea


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class HomeworkHelpRequest(BaseModel):
    subject: SubjectArea
    question: str = Field(..., min_length=5, max_length=5000)
    mode: HelpMode
    context: Optional[str] = Field(None, max_length=5000, description="Student's attempt (used for 'check' mode)")
    course_id: Optional[int] = None


class FollowUpRequest(BaseModel):
    session_id: int
    follow_up: str = Field(..., min_length=2, max_length=3000)


class SaveSolutionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    tags: Optional[list[str]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class HomeworkHelpResponse(BaseModel):
    session_id: int
    subject: SubjectArea
    mode: HelpMode
    question: str
    response: str
    steps: Optional[list[str]] = None
    hints: Optional[list[str]] = None

    model_config = {"from_attributes": True}


class FollowUpResponse(BaseModel):
    session_id: int
    response: str
    follow_up_count: int

    model_config = {"from_attributes": True}


class HomeworkSessionSummary(BaseModel):
    id: int
    subject: SubjectArea
    mode: HelpMode
    question: str
    response: str
    follow_up_count: int
    created_at: datetime
    is_saved: bool = False

    model_config = {"from_attributes": True}


class SavedSolutionOut(BaseModel):
    id: int
    session_id: int
    title: str
    tags: Optional[list[str]] = None
    subject: SubjectArea
    mode: HelpMode
    question: str
    response: str
    created_at: datetime

    model_config = {"from_attributes": True}
