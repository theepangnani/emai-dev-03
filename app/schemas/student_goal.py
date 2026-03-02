from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.student_goal import GoalCategory, GoalStatus


# ---------------------------------------------------------------------------
# GoalMilestone schemas
# ---------------------------------------------------------------------------


class GoalMilestoneCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    target_date: Optional[date] = None
    display_order: int = Field(default=0, ge=0)


class GoalMilestoneUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = None
    target_date: Optional[date] = None
    completed: Optional[bool] = None
    display_order: Optional[int] = Field(default=None, ge=0)


class GoalMilestoneResponse(BaseModel):
    id: int
    goal_id: int
    title: str
    description: Optional[str]
    target_date: Optional[date]
    completed: bool
    completed_at: Optional[datetime]
    display_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# StudentGoal schemas
# ---------------------------------------------------------------------------


class StudentGoalCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    category: GoalCategory = GoalCategory.ACADEMIC
    target_date: Optional[date] = None
    status: GoalStatus = GoalStatus.ACTIVE
    progress_pct: int = Field(default=0, ge=0, le=100)

    @field_validator("progress_pct")
    @classmethod
    def validate_progress(cls, v: int) -> int:
        if not 0 <= v <= 100:
            raise ValueError("progress_pct must be between 0 and 100")
        return v


class StudentGoalUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = None
    category: Optional[GoalCategory] = None
    target_date: Optional[date] = None
    status: Optional[GoalStatus] = None
    progress_pct: Optional[int] = Field(default=None, ge=0, le=100)

    @field_validator("progress_pct")
    @classmethod
    def validate_progress(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 0 <= v <= 100:
            raise ValueError("progress_pct must be between 0 and 100")
        return v


class StudentGoalResponse(BaseModel):
    id: int
    student_id: int
    title: str
    description: Optional[str]
    category: str
    target_date: Optional[date]
    status: str
    progress_pct: int
    created_at: datetime
    updated_at: datetime
    milestones: List[GoalMilestoneResponse] = []

    model_config = {"from_attributes": True}


class StudentGoalSummaryResponse(BaseModel):
    """Lightweight goal response without milestones list (for listings)."""
    id: int
    student_id: int
    title: str
    description: Optional[str]
    category: str
    target_date: Optional[date]
    status: str
    progress_pct: int
    created_at: datetime
    updated_at: datetime
    milestone_count: int = 0
    completed_milestone_count: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Progress update schema
# ---------------------------------------------------------------------------


class GoalProgressUpdate(BaseModel):
    progress_pct: int = Field(..., ge=0, le=100)
    note: Optional[str] = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# AI milestone suggestion response
# ---------------------------------------------------------------------------


class AIMilestoneSuggestion(BaseModel):
    title: str
    description: str
    suggested_target_date: Optional[date]


class AIMilestonesResponse(BaseModel):
    suggestions: List[AIMilestoneSuggestion]
    created_milestones: Optional[List[GoalMilestoneResponse]] = None
