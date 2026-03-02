"""Pydantic schemas for the Peer Review system."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Rubric
# ---------------------------------------------------------------------------

class RubricCriterion(BaseModel):
    criterion: str
    max_points: int
    description: str = ""


# ---------------------------------------------------------------------------
# PeerReviewAssignment
# ---------------------------------------------------------------------------

class PeerReviewAssignmentCreate(BaseModel):
    title: str
    instructions: str | None = None
    due_date: datetime | None = None
    is_anonymous: bool = True
    rubric: list[RubricCriterion] = []
    max_reviewers_per_student: int = 2
    course_id: int | None = None


class PeerReviewAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teacher_id: int
    course_id: int | None
    title: str
    instructions: str | None
    due_date: datetime | None
    is_anonymous: bool
    rubric: list[Any]
    max_reviewers_per_student: int
    reviews_released: bool
    created_at: datetime
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# PeerReviewSubmission
# ---------------------------------------------------------------------------

class PeerReviewSubmissionCreate(BaseModel):
    title: str
    content: str


class PeerReviewSubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    author_id: int
    title: str
    content: str
    file_key: str | None
    created_at: datetime
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# PeerReview
# ---------------------------------------------------------------------------

class PeerReviewCreate(BaseModel):
    """Student submitting a review for an allocation."""
    allocation_id: int
    scores: dict[str, float]  # {criterion_name: score}
    written_feedback: str | None = None


class PeerReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    submission_id: int
    reviewer_id: int
    scores: dict[str, Any] | None
    overall_score: float | None
    written_feedback: str | None
    status: str
    is_anonymous: bool
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class PeerReviewSummary(BaseModel):
    """Per-submission aggregate scores returned to teacher."""
    submission_id: int
    author_id: int
    author_name: str
    avg_score: float | None
    review_count: int
    criteria_averages: dict[str, float]  # {criterion: avg_score}
