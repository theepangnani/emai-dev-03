import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_

from app.core.config import settings
from app.core.utils import escape_like
from app.core.rate_limit import limiter, get_user_id_or_ip

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.course import Course
from app.models.assignment import Assignment
from app.models.audit_log import AuditLog
from app.models.broadcast import Broadcast
from app.models.course_content import CourseContent
from app.models.ai_usage_history import AIUsageHistory
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
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_users(
    request: Request,
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
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_stats(
    request: Request,
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

    total_materials = db.query(CourseContent).count()

    today = date.today()
    new_registrations_today = db.query(User).filter(
        func.date(User.created_at) == today
    ).count()

    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    ai_generations_last_hour = db.query(AIUsageHistory).filter(
        AIUsageHistory.created_at >= one_hour_ago
    ).count()

    return AdminStats(
        total_users=total_users,
        users_by_role=users_by_role,
        total_courses=total_courses,
        total_assignments=total_assignments,
        total_materials=total_materials,
        new_registrations_today=new_registrations_today,
        ai_generations_last_hour=ai_generations_last_hour,
    )


@router.get("/audit-logs", response_model=AuditLogList)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_audit_logs(
    request: Request,
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


@router.post("/users/{user_id}/unlock")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def unlock_user_account(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Manually unlock a locked user account. Admin only."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    was_locked = bool(user.locked_until) or (user.failed_login_attempts or 0) > 0
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_failed_login = None

    log_action(
        db,
        user_id=current_user.id,
        action="account_unlock",
        resource_type="user",
        resource_id=user.id,
        details={"was_locked": was_locked, "target_email": user.email},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    logger.info(
        "Admin %s unlocked user %s (was_locked=%s)",
        current_user.id, user.id, was_locked
    )

    return {"message": f"Account for {user.email or user.full_name} has been unlocked."}


class AddRoleRequest(BaseModel):
    role: str


class UpdateUserEmailRequest(BaseModel):
    email: str


@router.patch("/users/{user_id}/email", response_model=UserResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
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
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def add_role_to_user(
    request: Request,
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
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def remove_role_from_user(
    request: Request,
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
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
def send_broadcast(
    data: BroadcastCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Send a broadcast message to all active users with email."""
    # Count recipients first, then process in batches to avoid loading all users at once
    recipient_count = db.query(func.count(User.id)).filter(User.is_active == True).scalar()  # noqa: E712

    # Create broadcast record
    broadcast = Broadcast(
        sender_id=current_user.id,
        subject=data.subject,
        body=data.body,
        recipient_count=recipient_count,
        email_count=0,
    )
    db.add(broadcast)
    db.flush()

    # Process users in batches to avoid memory exhaustion
    BATCH_SIZE = 200
    message_content = f"[Broadcast] {data.subject}\n\n{data.body}"
    email_recipients: list[tuple[str, str]] = []
    offset = 0

    while True:
        batch = (
            db.query(User)
            .filter(User.is_active == True)  # noqa: E712
            .order_by(User.id)
            .offset(offset)
            .limit(BATCH_SIZE)
            .all()
        )
        if not batch:
            break

        for user in batch:
            db.add(Notification(
                user_id=user.id,
                type=NotificationType.SYSTEM,
                title=data.subject,
                content=data.body,
            ))
            if user.id != current_user.id:
                conv = _get_or_create_conversation(db, current_user.id, user.id, subject=data.subject)
                db.add(Message(
                    conversation_id=conv.id,
                    sender_id=current_user.id,
                    content=message_content,
                ))
            if user.email:
                email_recipients.append((user.email, user.full_name))

        offset += BATCH_SIZE

    log_action(
        db,
        user_id=current_user.id,
        action="broadcast_send",
        resource_type="broadcast",
        resource_id=broadcast.id,
        details={"subject": data.subject, "recipient_count": recipient_count},
        ip_address=request.client.host if request.client else None,
    )

    db.commit()

    # Build email batch and send via single SMTP connection
    email_batch = []
    for email, name in email_recipients:
        try:
            html = _render_broadcast_email(data.subject, data.body, name)
            html = add_inspiration_to_email(html, db, "parent")
            email_batch.append((email, f"ClassBridge: {data.subject}", html))
        except Exception:
            logger.warning("Failed to render broadcast email for %s", email)

    batch_result = send_emails_batch(email_batch)
    email_count = batch_result["sent"]

    broadcast.email_count = email_count
    db.commit()
    db.refresh(broadcast)

    logger.info("Broadcast %d: sent %d emails to %d users", broadcast.id, email_count, recipient_count)
    return broadcast


@router.get("/broadcasts", response_model=list[BroadcastListItem])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_broadcasts(
    request: Request,
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
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
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


# ── Feature Toggles ──────────────────────────────────────────────────

ALLOWED_VARIANTS = {"off", "on_50", "on_for_all"}


class FeatureToggleUpdate(BaseModel):
    enabled: bool | None = None
    variant: str | None = None  # 'off' | 'on_50' | 'on_for_all' (#3601)


@router.get("/features")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_feature_toggles(
    request: Request,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Get all feature flags (DB-backed + config-based)."""
    from app.models.feature_flag import FeatureFlag

    config_flags = [
        {"key": "google_classroom", "name": "Google Classroom", "description": "Google Classroom integration", "enabled": settings.google_classroom_enabled, "variant": None, "updated_at": None},
        {"key": "waitlist_enabled", "name": "Waitlist", "description": "Waitlist-gated registration flow", "enabled": settings.waitlist_enabled, "variant": None, "updated_at": None},
    ]
    db_flags = db.query(FeatureFlag).order_by(FeatureFlag.id).all()
    return config_flags + [
        {
            "key": f.key,
            "name": f.name,
            "description": f.description,
            "enabled": f.enabled,
            "variant": getattr(f, "variant", None) or "off",
            "updated_at": f.updated_at.isoformat() if f.updated_at else None,
        }
        for f in db_flags
    ]


@router.patch("/features/{feature_key}")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_feature_toggle(
    request: Request,
    feature_key: str,
    body: FeatureToggleUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Toggle a feature on or off and/or update its A/B variant.

    Accepts `enabled` (bool) and/or `variant` ('off'|'on_50'|'on_for_all').
    At least one field must be provided. (#3601)
    """
    from app.models.feature_flag import FeatureFlag

    if body.enabled is None and body.variant is None:
        raise HTTPException(status_code=400, detail="Must provide 'enabled' and/or 'variant'")

    if body.variant is not None and body.variant not in ALLOWED_VARIANTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid variant '{body.variant}'. Must be one of: {sorted(ALLOWED_VARIANTS)}",
        )

    # Handle legacy config-based flags (only support `enabled`, no variant)
    config_features = {"google_classroom": "google_classroom_enabled", "waitlist_enabled": "waitlist_enabled"}
    if feature_key in config_features:
        if body.variant is not None:
            raise HTTPException(
                status_code=400,
                detail=f"Config-based flag '{feature_key}' does not support variants",
            )
        attr = config_features[feature_key]
        setattr(settings, attr, body.enabled)
        log_action(
            db,
            user_id=current_user.id,
            action="update",
            resource_type="feature_toggle",
            details=f"{feature_key}={'enabled' if body.enabled else 'disabled'}",
        )
        db.commit()
        logger.info(f"Feature toggle '{feature_key}' set to {body.enabled} by admin {current_user.id}")
        return {"feature": feature_key, "enabled": body.enabled, "variant": None}

    # Handle DB-backed flags
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == feature_key).first()
    if not flag:
        raise HTTPException(status_code=404, detail=f"Unknown feature: {feature_key}")

    details_parts: list[str] = []
    if body.enabled is not None:
        flag.enabled = body.enabled
        details_parts.append(f"{feature_key}={'enabled' if body.enabled else 'disabled'}")
    if body.variant is not None:
        flag.variant = body.variant
        details_parts.append(f"variant={body.variant}")

    flag.updated_at = datetime.now(timezone.utc)
    log_action(
        db,
        user_id=current_user.id,
        action="update",
        resource_type="feature_toggle",
        details="; ".join(details_parts),
    )
    db.commit()

    logger.info(
        f"Feature toggle '{feature_key}' updated by admin {current_user.id}: "
        f"enabled={flag.enabled} variant={flag.variant}"
    )
    return {
        "feature": feature_key,
        "enabled": flag.enabled,
        "variant": getattr(flag, "variant", None) or "off",
    }


# --- Storage limit admin endpoints (#1007) ---


class StorageLimitsUpdate(BaseModel):
    storage_limit_bytes: int | None = None
    upload_limit_bytes: int | None = None


@router.get("/users/{user_id}/storage")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_user_storage(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """View storage usage for a specific user."""
    from app.services.storage_limits import get_storage_info
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    info = get_storage_info(user)
    info["user_id"] = user.id
    info["full_name"] = user.full_name
    info["email"] = user.email
    return info


@router.patch("/users/{user_id}/storage-limits")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_user_storage_limits(
    request: Request,
    user_id: int,
    body: StorageLimitsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Set custom storage limits for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.storage_limit_bytes is not None:
        if body.storage_limit_bytes < 0:
            raise HTTPException(status_code=400, detail="must be >= 0")
        user.storage_limit_bytes = body.storage_limit_bytes
    if body.upload_limit_bytes is not None:
        if body.upload_limit_bytes < 0:
            raise HTTPException(status_code=400, detail="must be >= 0")
        user.upload_limit_bytes = body.upload_limit_bytes
    log_action(
        db, user_id=current_user.id, action="update",
        resource_type="storage_limits", resource_id=user.id,
        details=f"storage_limit={body.storage_limit_bytes}, upload_limit={body.upload_limit_bytes}",
    )
    db.commit()

    from app.services.storage_limits import get_storage_info
    return get_storage_info(user)


@router.get("/storage/overview")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_storage_overview(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Platform-wide storage statistics."""
    total_used = db.query(func.coalesce(func.sum(User.storage_used_bytes), 0)).scalar()
    total_limit = db.query(func.coalesce(func.sum(User.storage_limit_bytes), 0)).scalar()
    user_count = db.query(func.count(User.id)).filter(User.storage_used_bytes > 0).scalar()
    total_users = db.query(func.count(User.id)).scalar()


    return {
        "total_storage_used_bytes": total_used,
        "total_storage_limit_bytes": total_limit,
        "users_with_files": user_count,
        "total_users": total_users,
        "avg_usage_bytes": total_used // max(user_count, 1),
    }


# ── XP Award Audit (#2005) ────────────────────────────────────


@router.get("/xp-awards")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_xp_awards(
    request: Request,
    awarder_id: int | None = None,
    student_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """List all brownie point awards (admin audit view)."""
    from app.models.xp import XpLedger

    query = db.query(XpLedger).filter(XpLedger.action_type == "brownie_points")

    if awarder_id is not None:
        query = query.filter(XpLedger.awarder_id == awarder_id)
    if student_id is not None:
        query = query.filter(XpLedger.student_id == student_id)
    if date_from:
        query = query.filter(XpLedger.created_at >= date_from)
    if date_to:
        query = query.filter(XpLedger.created_at <= date_to)

    total = query.count()
    rows = query.order_by(XpLedger.created_at.desc()).offset(skip).limit(limit).all()

    # Resolve user names
    user_ids = set()
    for r in rows:
        user_ids.add(r.student_id)
        if r.awarder_id:
            user_ids.add(r.awarder_id)
    user_map = {}
    if user_ids:
        users = db.query(User.id, User.full_name, User.role).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: {"name": u.full_name, "role": u.role} for u in users}

    items = []
    for r in rows:
        awarder_info = user_map.get(r.awarder_id, {}) if r.awarder_id else {}
        student_info = user_map.get(r.student_id, {})
        items.append({
            "id": r.id,
            "student_id": r.student_id,
            "student_name": student_info.get("name"),
            "awarder_id": r.awarder_id,
            "awarder_name": awarder_info.get("name"),
            "awarder_role": awarder_info.get("role"),
            "xp_awarded": r.xp_awarded,
            "reason": r.reason,
            "created_at": r.created_at,
        })

    return {"items": items, "total": total}




# ============================================
# Manual Migration Endpoint (#3079)
# ============================================

@router.post("/run-migrations")
@limiter.limit("5/minute", key_func=get_user_id_or_ip)
async def run_migrations_manual(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Run pending ALTER TABLE migrations on-demand.

    Needed because Cloud Run background migration thread can be blocked
    by PostgreSQL advisory locks from previous instances (#3079).
    """
    from sqlalchemy import text
    from app.db.database import engine

    results = []
    migrations = [
        ("course_contents", "detected_subject", "VARCHAR(50)"),
        ("course_contents", "detection_confidence", "DOUBLE PRECISION"),
        ("course_contents", "subject_confidence", "DOUBLE PRECISION"),
        ("course_contents", "template_key", "VARCHAR(50)"),
        ("course_contents", "classification_override", "BOOLEAN DEFAULT FALSE"),
        ("study_guides", "template_key", "VARCHAR(50)"),
        ("study_guides", "num_questions", "INTEGER"),
        ("study_guides", "difficulty", "VARCHAR(20)"),
        ("study_guides", "answer_key_markdown", "TEXT"),
        ("study_guides", "weak_topics", "TEXT"),
        ("study_guides", "ai_engine", "VARCHAR(20)"),
        ("parent_gmail_integrations", "whatsapp_phone", "VARCHAR(20)"),
        ("parent_gmail_integrations", "whatsapp_verified", "BOOLEAN DEFAULT FALSE"),
        ("parent_gmail_integrations", "whatsapp_otp_code", "VARCHAR(6)"),
        ("parent_gmail_integrations", "whatsapp_otp_expires_at", "TIMESTAMP"),
        # CB-DEMO-001 F2 (#3601, #3711) — recovery for feature_flags.variant
        # if the startup migration ever silently fails again.
        ("feature_flags", "variant", "VARCHAR(20) NOT NULL DEFAULT 'off'"),
    ]

    with engine.connect() as conn:
        for tbl, col, typ in migrations:
            try:
                conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {typ}"))
                results.append({"table": tbl, "column": col, "status": "added_or_exists"})
            except Exception as e:
                results.append({"table": tbl, "column": col, "status": "error", "detail": str(e)})
        conn.commit()

    return {"migrations_run": len(migrations), "results": results}


# ============================================
# Demo Sessions — CB-DEMO-001 B4 (#3606)
# ============================================

from io import StringIO
import csv as _csv

from fastapi.responses import StreamingResponse

from app.models.demo_session import DemoSession
from app.schemas.demo import AdminDemoSessionRow


_ALLOWED_DEMO_STATUSES = {"pending", "approved", "rejected", "blocklisted"}


def _serialize_demo_row(session: DemoSession) -> dict:
    """Build an AdminDemoSessionRow-compatible dict including moat summary."""
    moat = session.moat_engagement_json or {}
    moat_summary = {
        "tm_beats_seen": int(moat.get("tm_beats_seen", 0) or 0),
        "rs_roles_switched": int(moat.get("rs_roles_switched", 0) or 0),
        "pw_viewport_reached": bool(moat.get("pw_viewport_reached", False)),
    } if isinstance(moat, dict) else {
        "tm_beats_seen": 0,
        "rs_roles_switched": 0,
        "pw_viewport_reached": False,
    }

    return {
        "id": session.id,
        "created_at": session.created_at,
        "email": session.email,
        "full_name": session.full_name,
        "role": session.role,
        "verified": bool(session.verified),
        "verified_ts": session.verified_ts,
        "generations_count": session.generations_count or 0,
        "admin_status": session.admin_status,
        "source_ip_hash": session.source_ip_hash,
        "user_agent": session.user_agent,
        "archived_at": session.archived_at,
        "moat_engagement_json": session.moat_engagement_json,
        "moat_summary": moat_summary,
    }


@router.get("/demo-sessions")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_demo_sessions(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, description="Filter by admin_status"),
    verified: bool | None = Query(None, description="Filter by verified"),
    search: str | None = Query(None, description="Substring of email or full_name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Paginated list of demo sessions for admin review (FR-065)."""
    query = db.query(DemoSession)

    if status is not None:
        if status not in _ALLOWED_DEMO_STATUSES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {sorted(_ALLOWED_DEMO_STATUSES)}",
            )
        query = query.filter(DemoSession.admin_status == status)

    if verified is not None:
        query = query.filter(DemoSession.verified == verified)

    if search:
        pattern = f"%{escape_like(search)}%"
        query = query.filter(
            or_(
                DemoSession.email.ilike(pattern),
                DemoSession.full_name.ilike(pattern),
            )
        )

    total = query.count()
    offset = (page - 1) * per_page
    rows = (
        query.order_by(DemoSession.created_at.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    # All-time per-status counts, independent of current filters (#3703).
    count_rows = (
        db.query(DemoSession.admin_status, func.count(DemoSession.id))
        .group_by(DemoSession.admin_status)
        .all()
    )
    counts = {s: 0 for s in _ALLOWED_DEMO_STATUSES}
    for status_value, n in count_rows:
        if status_value in counts:
            counts[status_value] = int(n or 0)

    return {
        "items": [_serialize_demo_row(r) for r in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "counts": counts,
    }


def _set_demo_status(
    db: Session,
    session_id: str,
    new_status: str,
    current_user: User,
    request: Request,
    action: str,
) -> dict:
    row = db.query(DemoSession).filter(DemoSession.id == session_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Demo session not found")

    previous_status = row.admin_status
    row.admin_status = new_status

    log_action(
        db,
        user_id=current_user.id,
        action=action,
        resource_type="demo_session",
        resource_id=None,
        details={
            "demo_session_id": row.id,
            "email": row.email,
            "previous_status": previous_status,
            "new_status": new_status,
        },
        ip_address=request.client.host if request.client else None,
    )

    db.commit()
    db.refresh(row)
    return _serialize_demo_row(row)


@router.post("/demo-sessions/{session_id}/approve")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def approve_demo_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Mark a demo session as approved."""
    return _set_demo_status(
        db, session_id, "approved", current_user, request, "demo_session_approve"
    )


@router.post("/demo-sessions/{session_id}/reject")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def reject_demo_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Mark a demo session as rejected."""
    return _set_demo_status(
        db, session_id, "rejected", current_user, request, "demo_session_reject"
    )


@router.post("/demo-sessions/{session_id}/blocklist")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def blocklist_demo_session(
    session_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Mark a demo session as blocklisted."""
    return _set_demo_status(
        db, session_id, "blocklisted", current_user, request, "demo_session_blocklist"
    )


@router.get("/demo-sessions/export.csv")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def export_demo_sessions_csv(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Stream ALL demo session rows as CSV (FR-065).

    Uses a server-side cursor via `yield_per` so we do not buffer the
    entire table in memory.
    """
    log_action(
        db,
        user_id=current_user.id,
        action="demo_session_export_csv",
        resource_type="demo_session",
        resource_id=None,
        details={},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    columns = [
        "id",
        "created_at",
        "email",
        "full_name",
        "role",
        "verified",
        "verified_ts",
        "generations_count",
        "admin_status",
    ]

    def row_iter():
        buf = StringIO()
        writer = _csv.writer(buf)
        writer.writerow(columns)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        query = db.query(DemoSession).order_by(DemoSession.created_at.desc())
        for r in query.yield_per(500):
            writer.writerow([
                r.id,
                r.created_at.isoformat() if r.created_at else "",
                r.email or "",
                r.full_name or "",
                r.role or "",
                "true" if r.verified else "false",
                r.verified_ts.isoformat() if r.verified_ts else "",
                int(r.generations_count or 0),
                r.admin_status or "",
            ])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    filename = f"demo-sessions-{datetime.now().strftime('%Y-%m-%d')}.csv"
    return StreamingResponse(
        row_iter(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
