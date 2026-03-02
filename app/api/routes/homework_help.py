"""Homework Help API routes — AI-powered subject-specific tutoring."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.homework_help import HelpMode, HomeworkSavedSolution, HomeworkSession, SubjectArea
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.homework_help import (
    FollowUpRequest,
    FollowUpResponse,
    HomeworkHelpRequest,
    HomeworkHelpResponse,
    HomeworkSessionSummary,
    SaveSolutionRequest,
    SavedSolutionOut,
)
from app.services.homework_help import HomeworkHelpService, _parse_steps

router = APIRouter(prefix="/homework", tags=["homework-help"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_student_for_user(current_user: User, db: Session) -> Student:
    """Resolve the Student record for the authenticated user, or raise 403."""
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student profile not found",
        )
    return student


def _session_to_response(session: HomeworkSession) -> HomeworkHelpResponse:
    steps = _parse_steps(session.response)
    hints: list[str] = []
    if session.mode == HelpMode.HINT and steps:
        hints = steps

    return HomeworkHelpResponse(
        session_id=session.id,
        subject=session.subject,
        mode=session.mode,
        question=session.question,
        response=session.response,
        steps=steps if session.mode in (HelpMode.SOLVE, HelpMode.EXPLAIN) else None,
        hints=hints if session.mode == HelpMode.HINT else None,
    )


# ---------------------------------------------------------------------------
# POST /api/homework/help — get AI help
# ---------------------------------------------------------------------------

@router.post("/help", response_model=HomeworkHelpResponse)
def get_help(
    body: HomeworkHelpRequest,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Request AI homework help. Mode controls the tutoring style."""
    student = _get_student_for_user(current_user, db)
    try:
        session = HomeworkHelpService.get_help(
            student_id=student.id,
            subject=body.subject,
            question=body.question,
            mode=body.mode,
            context=body.context,
            course_id=body.course_id,
            db=db,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return _session_to_response(session)


# ---------------------------------------------------------------------------
# POST /api/homework/follow-up — continue the conversation
# ---------------------------------------------------------------------------

@router.post("/follow-up", response_model=FollowUpResponse)
def follow_up(
    body: FollowUpRequest,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Ask a follow-up question on an existing homework session."""
    student = _get_student_for_user(current_user, db)
    try:
        session = HomeworkHelpService.follow_up(
            session_id=body.session_id,
            student_id=student.id,
            follow_up=body.follow_up,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    return FollowUpResponse(
        session_id=session.id,
        response=session.response,
        follow_up_count=session.follow_up_count,
    )


# ---------------------------------------------------------------------------
# GET /api/homework/sessions — recent sessions
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=list[HomeworkSessionSummary])
def get_sessions(
    subject: Optional[SubjectArea] = None,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Retrieve the student's 50 most recent homework sessions, optionally filtered by subject."""
    student = _get_student_for_user(current_user, db)
    sessions = HomeworkHelpService.get_sessions(
        student_id=student.id,
        subject=subject,
        db=db,
    )
    # Gather saved session IDs so we can mark which ones have a saved solution
    saved_session_ids = {
        s.session_id
        for s in db.query(HomeworkSavedSolution.session_id)
        .filter(HomeworkSavedSolution.student_id == student.id)
        .all()
    }
    result = []
    for sess in sessions:
        result.append(
            HomeworkSessionSummary(
                id=sess.id,
                subject=sess.subject,
                mode=sess.mode,
                question=sess.question,
                response=sess.response,
                follow_up_count=sess.follow_up_count,
                created_at=sess.created_at,
                is_saved=sess.id in saved_session_ids,
            )
        )
    return result


# ---------------------------------------------------------------------------
# POST /api/homework/sessions/{id}/save — save a solution
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/save", response_model=SavedSolutionOut)
def save_solution(
    session_id: int,
    body: SaveSolutionRequest,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Save a homework session as a named solution for future reference."""
    student = _get_student_for_user(current_user, db)
    try:
        saved = HomeworkHelpService.save_solution(
            session_id=session_id,
            student_id=student.id,
            title=body.title,
            tags=body.tags,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    session = saved.session
    return SavedSolutionOut(
        id=saved.id,
        session_id=saved.session_id,
        title=saved.title,
        tags=saved.tags,
        subject=session.subject,
        mode=session.mode,
        question=session.question,
        response=session.response,
        created_at=saved.created_at,
    )


# ---------------------------------------------------------------------------
# GET /api/homework/saved — list saved solutions
# ---------------------------------------------------------------------------

@router.get("/saved", response_model=list[SavedSolutionOut])
def get_saved_solutions(
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Retrieve all saved solutions for the current student."""
    student = _get_student_for_user(current_user, db)
    saved_list = HomeworkHelpService.get_saved_solutions(student_id=student.id, db=db)
    result = []
    for saved in saved_list:
        session = saved.session
        result.append(
            SavedSolutionOut(
                id=saved.id,
                session_id=saved.session_id,
                title=saved.title,
                tags=saved.tags,
                subject=session.subject,
                mode=session.mode,
                question=session.question,
                response=session.response,
                created_at=saved.created_at,
            )
        )
    return result


# ---------------------------------------------------------------------------
# DELETE /api/homework/saved/{id} — delete saved solution
# ---------------------------------------------------------------------------

@router.delete("/saved/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_solution(
    saved_id: int,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Delete a saved homework solution."""
    student = _get_student_for_user(current_user, db)
    deleted = HomeworkHelpService.delete_saved_solution(
        saved_id=saved_id,
        student_id=student.id,
        db=db,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved solution not found")
