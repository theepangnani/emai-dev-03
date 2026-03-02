"""Lesson Summary API routes — AI-powered class notes summarization.

Routes:
  POST   /api/lesson-summary/generate       — generate AI summary from notes
  GET    /api/lesson-summary/               — list student's summaries
  GET    /api/lesson-summary/{id}           — get full summary
  PATCH  /api/lesson-summary/{id}           — update title / raw_input
  DELETE /api/lesson-summary/{id}           — delete
  POST   /api/lesson-summary/{id}/to-flashcards — convert key concepts to flashcard set
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.lesson_summary import (
    FlashcardsFromSummaryResponse,
    LessonSummaryListItem,
    LessonSummaryRequest,
    LessonSummaryResponse,
    LessonSummaryUpdateRequest,
)
from app.services import lesson_summary as svc

router = APIRouter(prefix="/lesson-summary", tags=["lesson-summary"])

_student_or_admin = require_role(UserRole.STUDENT, UserRole.ADMIN)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/generate",
    response_model=LessonSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate AI lesson summary from class notes",
)
async def generate_summary(
    payload: LessonSummaryRequest,
    current_user: User = Depends(_student_or_admin),
    db: Session = Depends(get_db),
):
    """
    Submit raw class notes or a transcript and receive an AI-structured summary
    with key concepts, study questions, action items, and important dates.
    """
    try:
        return await svc.generate_summary(
            student_id=current_user.id,
            title=payload.title,
            raw_input=payload.raw_input,
            input_type=payload.input_type,
            course_id=payload.course_id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/",
    response_model=List[LessonSummaryListItem],
    summary="List lesson summaries",
)
def list_summaries(
    course_id: Optional[int] = Query(None, description="Filter by course"),
    current_user: User = Depends(_student_or_admin),
    db: Session = Depends(get_db),
):
    """Return all lesson summaries for the authenticated student, most recent first."""
    return svc.get_summaries(
        student_id=current_user.id,
        course_id=course_id,
        db=db,
    )


@router.get(
    "/{summary_id}",
    response_model=LessonSummaryResponse,
    summary="Get full lesson summary",
)
def get_summary(
    summary_id: int,
    current_user: User = Depends(_student_or_admin),
    db: Session = Depends(get_db),
):
    """Return the full detail of a single lesson summary."""
    return svc.get_summary(summary_id=summary_id, student_id=current_user.id, db=db)


@router.patch(
    "/{summary_id}",
    response_model=LessonSummaryResponse,
    summary="Update lesson summary title or notes",
)
def update_summary(
    summary_id: int,
    payload: LessonSummaryUpdateRequest,
    current_user: User = Depends(_student_or_admin),
    db: Session = Depends(get_db),
):
    """Update the title and/or raw_input of an existing lesson summary."""
    return svc.update_summary(
        summary_id=summary_id,
        student_id=current_user.id,
        title=payload.title,
        raw_input=payload.raw_input,
        db=db,
    )


@router.delete(
    "/{summary_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete lesson summary",
)
def delete_summary(
    summary_id: int,
    current_user: User = Depends(_student_or_admin),
    db: Session = Depends(get_db),
):
    """Permanently delete a lesson summary."""
    svc.delete_summary(summary_id=summary_id, student_id=current_user.id, db=db)


@router.post(
    "/{summary_id}/to-flashcards",
    response_model=FlashcardsFromSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Convert key concepts to flashcard set",
)
def convert_to_flashcards(
    summary_id: int,
    current_user: User = Depends(_student_or_admin),
    db: Session = Depends(get_db),
):
    """
    Take the key_concepts from a lesson summary and create a StudyGuide flashcard
    set that the student can review or quiz themselves on.
    """
    return svc.generate_flashcards_from_summary(
        summary_id=summary_id,
        student_id=current_user.id,
        db=db,
    )
