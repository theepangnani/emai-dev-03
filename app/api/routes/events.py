"""API routes for detected assessment events."""
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.detected_event import DetectedEvent
from app.models.user import User, UserRole
from app.models.student import Student, parent_students
from app.schemas.detected_event import DetectedEventCreate, DetectedEventResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


def _get_student_user_ids(db: Session, current_user: User) -> list[int]:
    """Return list of user IDs whose events the current user can see."""
    if current_user.role == UserRole.STUDENT:
        return [current_user.id]
    if current_user.role == UserRole.PARENT:
        child_ids = (
            db.query(parent_students.c.student_id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        )
        student_ids = [row[0] for row in child_ids]
        user_ids = (
            db.query(Student.user_id)
            .filter(Student.id.in_(student_ids))
            .all()
        )
        return [row[0] for row in user_ids]
    return [current_user.id]


@router.get("/upcoming", response_model=list[DetectedEventResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_upcoming_events(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List upcoming events for current user (next 14 days, not dismissed)."""
    user_ids = _get_student_user_ids(db, current_user)
    today = date.today()
    cutoff = today + timedelta(days=14)

    events = (
        db.query(DetectedEvent)
        .filter(
            DetectedEvent.student_id.in_(user_ids),
            DetectedEvent.dismissed == False,  # noqa: E712
            DetectedEvent.event_date >= today,
            DetectedEvent.event_date <= cutoff,
        )
        .order_by(DetectedEvent.event_date.asc())
        .all()
    )

    result = []
    for event in events:
        resp = DetectedEventResponse.model_validate(event)
        resp.days_remaining = (event.event_date - today).days
        result.append(resp)

    return result


@router.post("", response_model=DetectedEventResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_event(
    request: Request,
    data: DetectedEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an event manually (student/parent)."""
    if current_user.role not in (UserRole.STUDENT, UserRole.PARENT):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students and parents can create events",
        )

    event = DetectedEvent(
        student_id=current_user.id,
        course_id=data.course_id,
        event_type=data.event_type,
        event_title=data.event_title,
        event_date=data.event_date,
        source=data.source,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    resp = DetectedEventResponse.model_validate(event)
    resp.days_remaining = (event.event_date - date.today()).days
    return resp


@router.delete("/{event_id}", status_code=status.HTTP_200_OK)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def dismiss_event(
    request: Request,
    event_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dismiss event (soft delete via dismissed=True)."""
    event = db.query(DetectedEvent).filter(DetectedEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    # Check ownership
    user_ids = _get_student_user_ids(db, current_user)
    if event.student_id not in user_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    event.dismissed = True
    db.commit()
    return {"detail": "Event dismissed"}
