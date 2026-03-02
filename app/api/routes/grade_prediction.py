"""AI Grade Prediction API routes.

POST  /api/grade-prediction/generate              — Student: generate predictions for all courses
POST  /api/grade-prediction/generate/{course_id}  — Student: generate for specific course
GET   /api/grade-prediction/                      — Student: list latest predictions
GET   /api/grade-prediction/{course_id}           — Student: get course prediction
GET   /api/grade-prediction/student/{student_id}  — Parent: child predictions
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_feature, require_role
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.grade_prediction import GradePredictionListResponse, GradePredictionResponse
from app.services.grade_prediction import GradePredictionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/grade-prediction", tags=["Grade Prediction"])

_service = GradePredictionService()


# ---------------------------------------------------------------------------
# Student routes
# ---------------------------------------------------------------------------


@router.post(
    "/generate",
    response_model=GradePredictionListResponse,
    summary="Generate grade predictions for all enrolled courses",
)
async def generate_predictions(
    _flag=Depends(require_feature("grade_tracking")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Generate (or refresh) AI grade predictions for every course the student is enrolled in."""
    predictions = await _service.predict_grade(current_user.id, db)
    if not predictions:
        return GradePredictionListResponse(predictions=[])

    # Rebuild list response with summary metrics
    return _service.get_predictions(current_user.id, db)


@router.post(
    "/generate/{course_id}",
    response_model=GradePredictionResponse,
    summary="Generate grade prediction for a specific course",
)
async def generate_course_prediction(
    course_id: int,
    _flag=Depends(require_feature("grade_tracking")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Generate (or refresh) an AI grade prediction for a single course."""
    results = await _service.predict_grade(current_user.id, db, course_id=course_id)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No prediction could be generated. Ensure you are enrolled in this course.",
        )
    return results[0]


@router.get(
    "/",
    response_model=GradePredictionListResponse,
    summary="List latest grade predictions for the current student",
)
def list_predictions(
    _flag=Depends(require_feature("grade_tracking")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Return the most recent grade prediction per course for the logged-in student."""
    return _service.get_predictions(current_user.id, db)


@router.get(
    "/student/{student_id}",
    response_model=GradePredictionListResponse,
    summary="Parent: view child grade predictions",
)
def get_child_predictions(
    student_id: int,
    _flag=Depends(require_feature("grade_tracking")),
    current_user: User = Depends(require_role(UserRole.PARENT)),
    db: Session = Depends(get_db),
):
    """Return grade predictions for a linked child (parent role only)."""
    result = _service.get_parent_predictions(current_user.id, student_id, db)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not linked to this student.",
        )
    return result


@router.get(
    "/{course_id}",
    response_model=GradePredictionResponse,
    summary="Get grade prediction for a specific course",
)
def get_course_prediction(
    course_id: int,
    _flag=Depends(require_feature("grade_tracking")),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Return the latest grade prediction for a specific course."""
    pred = _service.get_course_prediction(current_user.id, course_id, db)
    if pred is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No prediction found for this course. Generate one first.",
        )
    return pred
