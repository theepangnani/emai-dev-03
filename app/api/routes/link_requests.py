"""Link request routes for parent-student approval workflows."""
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, parent_students, RelationshipType
from app.models.link_request import LinkRequest, LinkRequestStatus, LinkRequestType
from app.models.notification import NotificationType
from app.schemas.link_request import (
    LinkRequestResponse,
    LinkRequestRespondRequest,
    LinkRequestCreateRequest,
    LinkRequestUserInfo,
)
from app.api.deps import get_current_user, require_role
from app.services.notification_service import send_multi_channel_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/link-requests", tags=["link-requests"])


def _build_response(lr: LinkRequest) -> LinkRequestResponse:
    """Convert a LinkRequest ORM object to a response schema."""
    return LinkRequestResponse(
        id=lr.id,
        request_type=lr.request_type,
        status=lr.status,
        requester=LinkRequestUserInfo(
            id=lr.requester.id,
            full_name=lr.requester.full_name,
            email=lr.requester.email,
        ),
        target=LinkRequestUserInfo(
            id=lr.target.id,
            full_name=lr.target.full_name,
            email=lr.target.email,
        ),
        student_id=lr.student_id,
        relationship_type=lr.relationship_type,
        message=lr.message,
        created_at=lr.created_at,
        expires_at=lr.expires_at,
        responded_at=lr.responded_at,
    )


@router.get("", response_model=list[LinkRequestResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_pending_link_requests(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List pending link requests where the current user is the target."""
    now = datetime.now(timezone.utc)
    requests = (
        db.query(LinkRequest)
        .filter(
            LinkRequest.target_user_id == current_user.id,
            LinkRequest.status == LinkRequestStatus.PENDING.value,
        )
        .order_by(LinkRequest.created_at.desc())
        .all()
    )

    # Filter out expired (mark them as expired in-place)
    result = []
    for lr in requests:
        expires = lr.expires_at.replace(tzinfo=None) if lr.expires_at.tzinfo else lr.expires_at
        if expires < now.replace(tzinfo=None):
            lr.status = LinkRequestStatus.EXPIRED.value
            continue
        result.append(_build_response(lr))

    if any(lr.status == LinkRequestStatus.EXPIRED.value for lr in requests):
        db.commit()

    return result


@router.get("/sent", response_model=list[LinkRequestResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_sent_link_requests(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List link requests sent by the current user."""
    requests = (
        db.query(LinkRequest)
        .filter(LinkRequest.requester_user_id == current_user.id)
        .order_by(LinkRequest.created_at.desc())
        .all()
    )
    return [_build_response(lr) for lr in requests]


@router.post("", response_model=LinkRequestResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def create_link_request(
    request: Request,
    body: LinkRequestCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Create a link request from a student to a parent by email."""
    # Find the student's Student record
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(status_code=400, detail="No student profile found for your account")

    # Look up the parent user by email
    parent = db.query(User).filter(User.email == body.parent_email).first()
    if not parent:
        raise HTTPException(
            status_code=404,
            detail="No account found with that email. Ask your parent to register first.",
        )

    if parent.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot send a link request to yourself")

    # Check if already linked
    existing_link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == parent.id,
            parent_students.c.student_id == student.id,
        )
        .first()
    )
    if existing_link:
        raise HTTPException(status_code=400, detail="You are already linked to this parent")

    # Check for existing pending request
    existing_request = (
        db.query(LinkRequest)
        .filter(
            LinkRequest.requester_user_id == current_user.id,
            LinkRequest.target_user_id == parent.id,
            LinkRequest.status == LinkRequestStatus.PENDING.value,
        )
        .first()
    )
    if existing_request:
        raise HTTPException(status_code=400, detail="You already have a pending request to this parent")

    # Create the link request
    lr = LinkRequest(
        request_type=LinkRequestType.STUDENT_TO_PARENT.value,
        status=LinkRequestStatus.PENDING.value,
        requester_user_id=current_user.id,
        target_user_id=parent.id,
        student_id=student.id,
        relationship_type=body.relationship_type,
        message=body.message,
        token=secrets.token_urlsafe(32),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(lr)
    db.flush()

    # Notify the parent
    send_multi_channel_notification(
        db=db,
        recipient=parent,
        sender=current_user,
        title="New Link Request",
        content=f"{current_user.full_name} wants to link as your student.",
        notification_type=NotificationType.LINK_REQUEST,
        link="/link-requests",
    )

    db.commit()
    db.refresh(lr)
    return _build_response(lr)


@router.post("/{request_id}/respond")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def respond_to_link_request(
    request: Request,
    request_id: int,
    body: LinkRequestRespondRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve or reject a link request."""
    lr = db.query(LinkRequest).filter(LinkRequest.id == request_id).first()
    if not lr:
        raise HTTPException(status_code=404, detail="Link request not found")

    if lr.target_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not the target of this request")

    if lr.status != LinkRequestStatus.PENDING.value:
        raise HTTPException(status_code=400, detail=f"Request already {lr.status}")

    # Check expiry
    now = datetime.now(timezone.utc)
    expires = lr.expires_at.replace(tzinfo=None) if lr.expires_at.tzinfo else lr.expires_at
    if expires < now.replace(tzinfo=None):
        lr.status = LinkRequestStatus.EXPIRED.value
        db.commit()
        raise HTTPException(status_code=400, detail="This link request has expired")

    requester = db.query(User).filter(User.id == lr.requester_user_id).first()

    if body.action == "approve":
        lr.status = LinkRequestStatus.APPROVED.value
        lr.responded_at = now

        # Determine parent and student based on request type
        if lr.request_type == "student_to_parent":
            parent_id = current_user.id
            student_id = lr.student_id
        else:  # parent_to_student
            parent_id = lr.requester_user_id
            # Find student record for the target user
            student = db.query(Student).filter(Student.user_id == current_user.id).first()
            student_id = student.id if student else lr.student_id

        # Insert into parent_students join table
        if student_id:
            rel_type = RelationshipType(lr.relationship_type or "guardian")
            # Check not already linked
            existing = (
                db.query(parent_students)
                .filter(
                    parent_students.c.parent_id == parent_id,
                    parent_students.c.student_id == student_id,
                )
                .first()
            )
            if not existing:
                db.execute(
                    insert(parent_students).values(
                        parent_id=parent_id,
                        student_id=student_id,
                        relationship_type=rel_type,
                    )
                )

        # Notify requester of approval
        if requester:
            send_multi_channel_notification(
                db=db,
                recipient=requester,
                sender=current_user,
                title="Link Request Approved",
                content=f"{current_user.full_name} has approved your link request.",
                notification_type=NotificationType.LINK_REQUEST,
                link="/link-requests",
            )

        db.commit()
        return {"message": "Link request approved", "status": "approved"}

    else:  # reject
        lr.status = LinkRequestStatus.REJECTED.value
        lr.responded_at = now

        # Notify requester of rejection
        if requester:
            send_multi_channel_notification(
                db=db,
                recipient=requester,
                sender=current_user,
                title="Link Request Declined",
                content=f"{current_user.full_name} has declined your link request.",
                notification_type=NotificationType.LINK_REQUEST,
                link="/link-requests",
            )

        db.commit()
        return {"message": "Link request rejected", "status": "rejected"}
