import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_

from app.core.config import settings
from app.core.utils import escape_like

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.course import Course
from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.broadcast import Broadcast
from app.models.message import Conversation, Message
from app.models.notification import Notification, NotificationType
from app.api.deps import require_role
from app.schemas.admin import (
    AdminUserList, AdminStats,
    BroadcastCreate, BroadcastResponse, BroadcastListItem,
    AdminMessageCreate, AdminMessageResponse,
)
from app.schemas.audit import AuditLogResponse, AuditLogList
from app.schemas.user import UserResponse
from app.services.audit_service import log_action
from app.services.email_service import send_email_sync, send_emails_batch, add_inspiration_to_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=AdminUserList)
def list_users(
    role: UserRole | None = None,
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List all users with optional role filter and search."""
    query = db.query(User)

    if role:
        query = query.filter(User.role == role)

    if search:
        search_term = f"%{escape_like(search)}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term),
            )
        )

    total = query.count()
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    return AdminUserList(users=users, total=total)


@router.get("/stats", response_model=AdminStats)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Get platform statistics."""
    total_users = db.query(User).count()

    # Count users who hold each role (checking multi-role 'roles' column)
    users_by_role: dict[str, int] = {}
    for r in UserRole:
        count = db.query(User).filter(
            or_(
                User.roles.contains(r.value),
                # Fallback for users with no roles column set
                (User.role == r) & (User.roles.is_(None) | (User.roles == "")),
            )
        ).count()
        if count:
            users_by_role[r.value] = count

    total_courses = db.query(Course).count()
    total_assignments = db.query(Assignment).count()

    return AdminStats(
        total_users=total_users,
        users_by_role=users_by_role,
        total_courses=total_courses,
        total_assignments=total_assignments,
    )


@router.get("/audit-logs", response_model=AuditLogList)
def list_audit_logs(
    user_id: int | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List audit logs with filters. Admin only."""
    query = db.query(AuditLog)

    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if resource_type:
        query = query.filter(AuditLog.resource_type == resource_type)
    if date_from:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to:
        query = query.filter(AuditLog.created_at <= date_to)
    if search:
        search_term = f"%{escape_like(search)}%"
        query = query.filter(AuditLog.details.ilike(search_term))

    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()

    # Resolve user names in bulk
    user_ids = {log.user_id for log in logs if log.user_id}
    user_map = {}
    if user_ids:
        users = db.query(User.id, User.full_name).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: u.full_name for u in users}

    items = [
        AuditLogResponse(
            id=log.id,
            user_id=log.user_id,
            user_name=user_map.get(log.user_id) if log.user_id else None,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log in logs
    ]

    return AuditLogList(items=items, total=total)


class AddRoleRequest(BaseModel):
    role: str


class UpdateUserEmailRequest(BaseModel):
    email: str


@router.patch("/users/{user_id}/email", response_model=UserResponse)
def update_user_email(
    user_id: int,
    data: UpdateUserEmailRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update a user's email address with cascade updates to related records.

    This endpoint:
    1. Updates the user's email
    2. Updates any pending invites sent TO the old email
    3. Logs the change in audit log
    """
    from app.models.invite import Invite
    from pydantic import EmailStr, ValidationError

    # Validate email format
    try:
        EmailStr._validate(data.email)  # type: ignore
    except ValidationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email format")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_email = user.email
    new_email = data.email.lower().strip()

    if old_email == new_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already set to this value")

    # Check if new email is already taken
    existing = db.query(User).filter(User.email == new_email, User.id != user_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use by another user")

    # CASCADE UPDATE: Update pending invites sent TO the old email
    updated_invites = (
        db.query(Invite)
        .filter(
            Invite.email == old_email,
            Invite.accepted_at.is_(None),  # Only pending invites
        )
        .update({"email": new_email}, synchronize_session=False)
    )

    # Update the user's email
    user.email = new_email

    # Log the change
    log_action(
        db,
        user_id=current_user.id,
        action="user_email_update",
        resource_type="user",
        resource_id=user.id,
        details={
            "old_email": old_email,
            "new_email": new_email,
            "updated_invites": updated_invites,
        },
        ip_address=request.client.host if request.client else None,
    )

    db.commit()
    db.refresh(user)

    logger.info(
        f"Admin {current_user.id} updated user {user.id} email: {old_email} → {new_email}. "
        f"Updated {updated_invites} pending invite(s)."
    )

    return user


@router.post("/users/{user_id}/add-role", response_model=UserResponse)
def add_role_to_user(
    user_id: int,
    data: AddRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Add a role to a user. Also creates the Teacher/Student profile record if needed."""
    try:
        new_role = UserRole(data.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {data.role}")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.has_role(new_role):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User already has the '{data.role}' role")

    # Update roles column
    current_roles = user.get_roles_list()
    current_roles.append(new_role)
    user.set_roles(current_roles)

    # Create profile record if needed
    from app.services.user_service import ensure_profile_records
    ensure_profile_records(db, user)

    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/remove-role", response_model=UserResponse)
def remove_role_from_user(
    user_id: int,
    data: AddRoleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Remove a role from a user. Cannot remove their last role."""
    try:
        target_role = UserRole(data.role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {data.role}")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not user.has_role(target_role):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"User does not have the '{data.role}' role")

    current_roles = user.get_roles_list()
    if len(current_roles) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the user's only role")

    current_roles = [r for r in current_roles if r != target_role]
    user.set_roles(current_roles)

    # If active role was removed, switch to first remaining role
    if user.role == target_role:
        user.role = current_roles[0]

    db.commit()
    db.refresh(user)
    return user


# ── Admin Messaging ──────────────────────────────────────────

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"


def _get_or_create_conversation(
    db: Session, admin_id: int, user_id: int, subject: str | None = None
) -> Conversation:
    """Find existing conversation between admin and user, or create one."""
    conv = (
        db.query(Conversation)
        .filter(
            or_(
                and_(
                    Conversation.participant_1_id == admin_id,
                    Conversation.participant_2_id == user_id,
                ),
                and_(
                    Conversation.participant_1_id == user_id,
                    Conversation.participant_2_id == admin_id,
                ),
            )
        )
        .first()
    )
    if not conv:
        conv = Conversation(
            participant_1_id=admin_id,
            participant_2_id=user_id,
            subject=subject,
        )
        db.add(conv)
        db.flush()
    return conv


def _render_broadcast_email(subject: str, body: str, recipient_name: str) -> str:
    import html as _html
    template_path = TEMPLATE_DIR / "admin_broadcast.html"
    tpl = template_path.read_text()
    # Convert plain text body to HTML: escape special chars, then convert newlines to <br>
    body_html = _html.escape(body).replace("\n", "<br>\n")
    return (
        tpl.replace("{{subject}}", _html.escape(subject))
        .replace("{{body}}", body_html)
        .replace("{{recipient_name}}", _html.escape(recipient_name))
        .replace("{{app_url}}", settings.frontend_url)
    )


@router.post("/broadcast", response_model=BroadcastResponse)
def send_broadcast(
    data: BroadcastCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Send a broadcast message to all active users with email."""
    active_users = db.query(User).filter(User.is_active == True).all()  # noqa: E712

    # Create broadcast record
    broadcast = Broadcast(
        sender_id=current_user.id,
        subject=data.subject,
        body=data.body,
        recipient_count=len(active_users),
        email_count=0,
    )
    db.add(broadcast)
    db.flush()

    # Create in-app notifications + conversation messages for all active users
    message_content = f"[Broadcast] {data.subject}\n\n{data.body}"
    for user in active_users:
        db.add(Notification(
            user_id=user.id,
            type=NotificationType.SYSTEM,
            title=data.subject,
            content=data.body,
        ))
        # Also create a conversation message so it appears in Messages page
        if user.id != current_user.id:
            conv = _get_or_create_conversation(db, current_user.id, user.id, subject=data.subject)
            db.add(Message(
                conversation_id=conv.id,
                sender_id=current_user.id,
                content=message_content,
            ))

    log_action(
        db,
        user_id=current_user.id,
        action="broadcast_send",
        resource_type="broadcast",
        resource_id=broadcast.id,
        details={"subject": data.subject, "recipient_count": len(active_users)},
        ip_address=request.client.host if request.client else None,
    )

    # Extract email data BEFORE commit (avoids N+1 lazy loads after expire_on_commit)
    email_recipients = [
        (user.email, user.full_name)
        for user in active_users
        if user.email
    ]

    db.commit()

    # Build email batch and send via single SMTP connection
    email_batch = []
    for email, name in email_recipients:
        try:
            html = _render_broadcast_email(data.subject, data.body, name)
            email_batch.append((email, f"ClassBridge: {data.subject}", html))
        except Exception:
            logger.warning("Failed to render broadcast email for %s", email)

    email_count = send_emails_batch(email_batch)

    broadcast.email_count = email_count
    db.commit()
    db.refresh(broadcast)

    logger.info("Broadcast %d: sent %d emails to %d users", broadcast.id, email_count, len(active_users))
    return broadcast


@router.get("/broadcasts", response_model=list[BroadcastListItem])
def list_broadcasts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List past broadcast messages."""
    broadcasts = (
        db.query(Broadcast)
        .order_by(Broadcast.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return broadcasts


@router.post("/users/{user_id}/message", response_model=AdminMessageResponse)
def send_admin_message(
    user_id: int,
    data: AdminMessageCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Send an individual message to a specific user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Create in-app notification
    db.add(Notification(
        user_id=user.id,
        type=NotificationType.SYSTEM,
        title=data.subject,
        content=data.body,
    ))

    # Create conversation message so it appears in Messages page
    conv = _get_or_create_conversation(db, current_user.id, user.id, subject=data.subject)
    message_content = f"[Admin Message] {data.subject}\n\n{data.body}"
    db.add(Message(
        conversation_id=conv.id,
        sender_id=current_user.id,
        content=message_content,
    ))

    log_action(
        db,
        user_id=current_user.id,
        action="admin_message_send",
        resource_type="user",
        resource_id=user.id,
        details={"subject": data.subject, "recipient": user.full_name},
        ip_address=request.client.host if request.client else None,
    )

    db.commit()

    # Send email if user has an email address
    email_sent = False
    if user.email:
        try:
            html = _render_broadcast_email(data.subject, data.body, user.full_name)
            html = add_inspiration_to_email(html, db, user.role)
            email_sent = send_email_sync(user.email, f"ClassBridge: {data.subject}", html)
        except Exception:
            logger.warning("Failed to send admin message email to user %s", user.id)

    return AdminMessageResponse(success=True, email_sent=email_sent)
