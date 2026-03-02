"""Quiz Assignments API — parent-assigned quizzes with complexity levels (#664).

Routes:
  POST   /api/quiz-assignments/               — parent assigns a quiz to their child
  GET    /api/quiz-assignments/               — list assignments (role-scoped)
  PATCH  /api/quiz-assignments/{id}/complete  — student marks complete with score
  DELETE /api/quiz-assignments/{id}           — parent cancels assignment
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.notification import Notification, NotificationType
from app.models.quiz_assignment import QuizAssignment
from app.api.deps import get_current_user, require_feature
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.schemas.quiz_assignment import (
    QuizAssignmentCreate,
    QuizAssignmentComplete,
    QuizAssignmentResponse,
)
from app.services.notification_service import send_multi_channel_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/quiz-assignments", tags=["Quiz Assignments"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_response(qa: QuizAssignment) -> QuizAssignmentResponse:
    """Construct a response DTO with joined fields."""
    study_guide_title: str | None = None
    course_name: str | None = None
    student_name: str | None = None

    if qa.study_guide:
        study_guide_title = qa.study_guide.title
        if qa.study_guide.course:
            course_name = qa.study_guide.course.name

    if qa.student and qa.student.user:
        student_name = qa.student.user.full_name

    return QuizAssignmentResponse(
        id=qa.id,
        parent_user_id=qa.parent_user_id,
        student_id=qa.student_id,
        study_guide_id=qa.study_guide_id,
        difficulty=qa.difficulty,
        due_date=qa.due_date,
        assigned_at=qa.assigned_at,
        completed_at=qa.completed_at,
        score=qa.score,
        attempt_count=qa.attempt_count,
        status=qa.status,
        note=qa.note,
        study_guide_title=study_guide_title,
        course_name=course_name,
        student_name=student_name,
    )


def _assert_parent_owns_student(db: Session, parent_user_id: int, student_id: int) -> Student:
    """Raise 403 unless the parent has a linked relationship with the student."""
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == parent_user_id,
            parent_students.c.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not linked to this student",
        )
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


# ---------------------------------------------------------------------------
# POST /api/quiz-assignments/
# ---------------------------------------------------------------------------


@router.post("/", response_model=QuizAssignmentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def assign_quiz(
    request: Request,
    body: QuizAssignmentCreate,
    _flag=Depends(require_feature("ai_study_tools")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parent assigns a quiz to their child.

    Validates:
    - Caller must be a PARENT.
    - The student must be linked to this parent.
    - The study guide must exist and have guide_type == 'quiz'.

    Creates an in-app notification for the child.
    """
    if current_user.role != UserRole.PARENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only parents can assign quizzes")

    student = _assert_parent_owns_student(db, current_user.id, body.student_id)

    # Validate study guide
    guide = db.query(StudyGuide).filter(StudyGuide.id == body.study_guide_id).first()
    if not guide:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study guide not found")
    if guide.guide_type != "quiz":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The selected study guide is not a quiz. Only quiz-type guides can be assigned.",
        )

    # Create assignment
    qa = QuizAssignment(
        parent_user_id=current_user.id,
        student_id=body.student_id,
        study_guide_id=body.study_guide_id,
        difficulty=body.difficulty,
        due_date=body.due_date,
        note=body.note,
        status="assigned",
        attempt_count=0,
    )
    db.add(qa)
    db.flush()  # get ID before sending notification

    # Notify the student
    student_user = student.user
    if student_user:
        difficulty_label = body.difficulty.capitalize()
        note_suffix = f" Note: {body.note}" if body.note else ""
        content = (
            f"{current_user.full_name} has assigned you a quiz: \"{guide.title}\" "
            f"(Difficulty: {difficulty_label}).{note_suffix}"
        )
        send_multi_channel_notification(
            db=db,
            recipient=student_user,
            sender=current_user,
            title="New Quiz Assigned",
            content=content,
            notification_type=NotificationType.SYSTEM,
            link="/dashboard",
            channels=["app_notification"],
            source_type="quiz_assignment",
            source_id=qa.id,
        )

    db.commit()
    db.refresh(qa)

    logger.info(
        f"Parent {current_user.id} assigned quiz {guide.id} to student {body.student_id} "
        f"(difficulty={body.difficulty})"
    )
    return _build_response(qa)


# ---------------------------------------------------------------------------
# GET /api/quiz-assignments/
# ---------------------------------------------------------------------------


@router.get("/", response_model=list[QuizAssignmentResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_quiz_assignments(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    student_id: int | None = Query(default=None),
    _flag=Depends(require_feature("ai_study_tools")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List quiz assignments, role-scoped.

    - PARENT: sees assignments they created. Can filter by student_id.
    - STUDENT: sees assignments assigned to them (via linked Student profile).
    - Other roles: 403.
    """
    q = db.query(QuizAssignment)

    if current_user.role == UserRole.PARENT:
        q = q.filter(QuizAssignment.parent_user_id == current_user.id)
        if student_id is not None:
            q = q.filter(QuizAssignment.student_id == student_id)

    elif current_user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            return []
        q = q.filter(QuizAssignment.student_id == student.id)

    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    if status_filter:
        q = q.filter(QuizAssignment.status == status_filter)

    assignments = q.order_by(QuizAssignment.assigned_at.desc()).all()
    return [_build_response(qa) for qa in assignments]


# ---------------------------------------------------------------------------
# PATCH /api/quiz-assignments/{id}/complete
# ---------------------------------------------------------------------------


@router.patch("/{assignment_id}/complete", response_model=QuizAssignmentResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def complete_quiz_assignment(
    request: Request,
    assignment_id: int,
    body: QuizAssignmentComplete,
    _flag=Depends(require_feature("ai_study_tools")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student marks a quiz assignment as complete with a score.

    - Only the assigned student may call this endpoint.
    - Increments attempt_count, sets completed_at and status.
    - Sends an in-app notification to the parent.
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can complete quiz assignments")

    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")

    qa = db.query(QuizAssignment).filter(
        QuizAssignment.id == assignment_id,
        QuizAssignment.student_id == student.id,
    ).first()
    if not qa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz assignment not found")

    qa.score = body.score
    qa.completed_at = datetime.now(timezone.utc)
    qa.status = "completed"
    qa.attempt_count = (qa.attempt_count or 0) + 1

    # Notify the parent
    parent_user = db.query(User).filter(User.id == qa.parent_user_id).first()
    if parent_user:
        guide_title = qa.study_guide.title if qa.study_guide else "quiz"
        content = (
            f"{current_user.full_name} completed the quiz \"{guide_title}\" "
            f"with a score of {body.score:.0f}%."
        )
        send_multi_channel_notification(
            db=db,
            recipient=parent_user,
            sender=current_user,
            title="Quiz Completed",
            content=content,
            notification_type=NotificationType.SYSTEM,
            link="/dashboard",
            channels=["app_notification"],
            source_type="quiz_assignment",
            source_id=qa.id,
            student_id=student.id,
        )

    db.commit()
    db.refresh(qa)

    logger.info(
        f"Student {current_user.id} completed quiz assignment {assignment_id} "
        f"(score={body.score}, attempt={qa.attempt_count})"
    )
    return _build_response(qa)


# ---------------------------------------------------------------------------
# DELETE /api/quiz-assignments/{id}
# ---------------------------------------------------------------------------


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def cancel_quiz_assignment(
    request: Request,
    assignment_id: int,
    _flag=Depends(require_feature("ai_study_tools")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Parent cancels a quiz assignment (only if not yet completed)."""
    if current_user.role != UserRole.PARENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only parents can cancel quiz assignments")

    qa = db.query(QuizAssignment).filter(
        QuizAssignment.id == assignment_id,
        QuizAssignment.parent_user_id == current_user.id,
    ).first()
    if not qa:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz assignment not found")

    if qa.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot cancel a completed quiz assignment",
        )

    db.delete(qa)
    db.commit()
    logger.info(f"Parent {current_user.id} cancelled quiz assignment {assignment_id}")
