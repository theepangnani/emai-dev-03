"""Study Request endpoints — parent-initiated study suggestions for students."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.notification import Notification, NotificationType
from app.models.study_request import StudyRequest
from app.models.student import parent_students
from app.models.user import User, UserRole
from app.api.deps import require_role, get_current_user
from app.schemas.study_request import (
    StudyRequestCreate,
    StudyRequestPendingCount,
    StudyRequestRespond,
    StudyRequestResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/study-requests", tags=["Study Requests"])


def _verify_parent_child(db: Session, parent_id: int, student_user_id: int) -> bool:
    """Return True if parent_id is linked to the student with the given user_id."""
    from app.models.student import Student

    student_rec = db.query(Student).filter(Student.user_id == student_user_id).first()
    if not student_rec:
        return False
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == parent_id,
            parent_students.c.student_id == student_rec.id,
        )
        .first()
    )
    return link is not None


def _to_response(sr: StudyRequest) -> StudyRequestResponse:
    return StudyRequestResponse(
        id=sr.id,
        parent_id=sr.parent_id,
        student_id=sr.student_id,
        subject=sr.subject,
        topic=sr.topic,
        urgency=sr.urgency,
        message=sr.message,
        status=sr.status,
        student_response=sr.student_response,
        responded_at=sr.responded_at,
        created_at=sr.created_at,
        parent_name=sr.parent.full_name if sr.parent else None,
    )


@router.post("", response_model=StudyRequestResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_study_request(
    request: Request,
    body: StudyRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Parent creates a study request for their child."""
    if not _verify_parent_child(db, current_user.id, body.student_id):
        raise HTTPException(status_code=403, detail="This student is not linked to your account")

    # Verify student user exists
    student_user = db.query(User).filter(User.id == body.student_id).first()
    if not student_user:
        raise HTTPException(status_code=404, detail="Student not found")

    sr = StudyRequest(
        parent_id=current_user.id,
        student_id=body.student_id,
        subject=body.subject,
        topic=body.topic,
        urgency=body.urgency,
        message=body.message,
    )
    db.add(sr)
    db.flush()

    # Notify the student
    topic_text = f" ({body.topic})" if body.topic else ""
    notification = Notification(
        user_id=body.student_id,
        type=NotificationType.PARENT_REQUEST,
        title=f"Study suggestion: {body.subject}{topic_text}",
        content=f"Your parent suggested reviewing {body.subject}{topic_text}. Tap to respond.",
        link=f"/study-requests",
        source_type="study_request",
        source_id=sr.id,
    )
    db.add(notification)
    db.commit()
    db.refresh(sr)

    return _to_response(sr)


@router.get("/pending", response_model=StudyRequestPendingCount)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def pending_count(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get count of pending study requests for the current student."""
    count = (
        db.query(StudyRequest)
        .filter(
            StudyRequest.student_id == current_user.id,
            StudyRequest.status == "pending",
        )
        .count()
    )
    return StudyRequestPendingCount(count=count)


@router.get("", response_model=list[StudyRequestResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_study_requests(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List study requests — parent sees sent, student sees received."""
    if current_user.role == UserRole.PARENT:
        rows = (
            db.query(StudyRequest)
            .filter(StudyRequest.parent_id == current_user.id)
            .order_by(StudyRequest.created_at.desc())
            .all()
        )
    else:
        rows = (
            db.query(StudyRequest)
            .filter(StudyRequest.student_id == current_user.id)
            .order_by(StudyRequest.created_at.desc())
            .all()
        )
    return [_to_response(sr) for sr in rows]


@router.get("/{request_id}", response_model=StudyRequestResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_study_request(
    request: Request,
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single study request."""
    sr = db.query(StudyRequest).filter(StudyRequest.id == request_id).first()
    if not sr:
        raise HTTPException(status_code=404, detail="Study request not found")
    if sr.parent_id != current_user.id and sr.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return _to_response(sr)


@router.patch("/{request_id}/respond", response_model=StudyRequestResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def respond_study_request(
    request: Request,
    request_id: int,
    body: StudyRequestRespond,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student responds to a study request (accept/defer/complete)."""
    sr = db.query(StudyRequest).filter(StudyRequest.id == request_id).first()
    if not sr:
        raise HTTPException(status_code=404, detail="Study request not found")
    if sr.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the student can respond")

    sr.status = body.status
    sr.student_response = body.response
    sr.responded_at = datetime.now(timezone.utc)
    db.flush()

    # Notify the parent
    status_labels = {"accepted": "accepted", "deferred": "deferred", "completed": "marked as done"}
    status_text = status_labels.get(body.status, body.status)
    notification = Notification(
        user_id=sr.parent_id,
        type=NotificationType.PARENT_REQUEST,
        title=f"{current_user.full_name} {status_text} your study suggestion",
        content=body.response or f"{current_user.full_name} {status_text}: {sr.subject}",
        link=f"/my-kids",
        source_type="study_request",
        source_id=sr.id,
    )
    db.add(notification)
    db.commit()
    db.refresh(sr)

    return _to_response(sr)
