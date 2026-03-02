import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.database import get_db
from app.models.user import User
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.notification import Notification
from app.models.notification_suppression import NotificationSuppression
from app.schemas.notification import (
    NotificationResponse,
    NotificationPreferences,
    NotificationSuppressionResponse,
    UnreadCountResponse,
)
from app.api.deps import get_current_user, require_feature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=list[NotificationResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_notifications(
    request: Request,
    _flag=Depends(require_feature("notification_system")),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    unread_only: bool = Query(False),
    status: str | None = Query(None, description="Filter: 'unread' (not acknowledged), 'acked', or 'all'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List notifications for the current user, newest first.

    Supports filtering by status:
    - status=unread  — only non-acknowledged notifications (acked_at IS NULL)
    - status=acked   — only acknowledged notifications
    - status=all     — all notifications (default)

    The legacy unread_only parameter filters by the 'read' boolean field.
    """
    q = db.query(Notification).filter(Notification.user_id == current_user.id)

    # Apply status filter (ACK-based)
    if status == "unread":
        q = q.filter(Notification.acked_at.is_(None))
    elif status == "acked":
        q = q.filter(Notification.acked_at.isnot(None))

    # Legacy filter (read-based)
    if unread_only:
        q = q.filter(Notification.read == False)

    notifications = q.order_by(desc(Notification.created_at)).offset(skip).limit(limit).all()
    return notifications


@router.get("/unread-count", response_model=UnreadCountResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_unread_count(
    request: Request,
    _flag=Depends(require_feature("notification_system")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the number of unread notifications."""
    count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.read == False,
        )
        .count()
    )
    return UnreadCountResponse(count=count)


@router.put("/{notification_id}/read", response_model=NotificationResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def mark_as_read(
    request: Request,
    notification_id: int,
    _flag=Depends(require_feature("notification_system")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification as read."""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.read = True
    db.commit()
    db.refresh(notification)
    return notification


@router.put("/{notification_id}/ack", response_model=NotificationResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def acknowledge_notification(
    request: Request,
    notification_id: int,
    _flag=Depends(require_feature("notification_system")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Acknowledge a notification that requires acknowledgement."""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if not notification.requires_ack:
        raise HTTPException(status_code=400, detail="This notification does not require acknowledgement")

    notification.acked_at = datetime.now(timezone.utc)
    notification.next_reminder_at = None
    notification.read = True
    db.commit()
    db.refresh(notification)
    return notification


@router.put("/{notification_id}/suppress", response_model=NotificationResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def suppress_notification(
    request: Request,
    notification_id: int,
    _flag=Depends(require_feature("notification_system")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suppress future notifications from the same source. Also ACKs and marks as read."""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    if not notification.source_type or not notification.source_id:
        raise HTTPException(status_code=400, detail="This notification has no source to suppress")

    # Check for existing suppression before insert (safe against unique constraint race)
    existing = (
        db.query(NotificationSuppression)
        .filter(
            NotificationSuppression.user_id == current_user.id,
            NotificationSuppression.source_type == notification.source_type,
            NotificationSuppression.source_id == notification.source_id,
        )
        .first()
    )
    if not existing:
        suppression = NotificationSuppression(
            user_id=current_user.id,
            source_type=notification.source_type,
            source_id=notification.source_id,
        )
        db.add(suppression)

    # Also ACK + mark read
    notification.acked_at = datetime.now(timezone.utc)
    notification.next_reminder_at = None
    notification.read = True
    db.commit()
    db.refresh(notification)
    return notification


@router.put("/read-all")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def mark_all_as_read(
    request: Request,
    _flag=Depends(require_feature("notification_system")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all notifications as read."""
    updated = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.read == False,
        )
        .update({"read": True})
    )
    db.commit()
    logger.info(f"Marked {updated} notifications as read for user {current_user.id}")
    return {"status": "ok", "marked_read": updated}


@router.delete("/{notification_id}")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_notification(
    request: Request,
    notification_id: int,
    _flag=Depends(require_feature("notification_system")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a notification."""
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    db.delete(notification)
    db.commit()
    return {"status": "ok"}


@router.get("/settings", response_model=NotificationPreferences)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_notification_settings(
    request: Request,
    _flag=Depends(require_feature("notification_system")),
    current_user: User = Depends(get_current_user),
):
    """Get notification preferences for the current user."""
    return NotificationPreferences(
        email_notifications=current_user.email_notifications
        if current_user.email_notifications is not None
        else True,
        assignment_reminder_days=current_user.assignment_reminder_days or "1,3",
        task_reminder_days=current_user.task_reminder_days or "1,3",
    )


@router.put("/settings", response_model=NotificationPreferences)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_notification_settings(
    request: Request,
    prefs: NotificationPreferences,
    _flag=Depends(require_feature("notification_system")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update notification preferences."""
    current_user.email_notifications = prefs.email_notifications
    current_user.assignment_reminder_days = prefs.assignment_reminder_days
    current_user.task_reminder_days = prefs.task_reminder_days
    db.commit()
    db.refresh(current_user)

    logger.info(
        f"Updated notification settings for user {current_user.id} | "
        f"email={prefs.email_notifications} | assignment_days={prefs.assignment_reminder_days} | "
        f"task_days={prefs.task_reminder_days}"
    )

    return prefs


@router.get("/suppressions", response_model=list[NotificationSuppressionResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_suppressions(
    request: Request,
    _flag=Depends(require_feature("notification_system")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all notification suppressions for the current user."""
    suppressions = (
        db.query(NotificationSuppression)
        .filter(NotificationSuppression.user_id == current_user.id)
        .order_by(desc(NotificationSuppression.suppressed_at))
        .all()
    )
    return suppressions


@router.delete("/suppressions/{suppression_id}")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_suppression(
    request: Request,
    suppression_id: int,
    _flag=Depends(require_feature("notification_system")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a notification suppression to re-enable notifications from that source."""
    suppression = (
        db.query(NotificationSuppression)
        .filter(
            NotificationSuppression.id == suppression_id,
            NotificationSuppression.user_id == current_user.id,
        )
        .first()
    )
    if not suppression:
        raise HTTPException(status_code=404, detail="Suppression not found")

    db.delete(suppression)
    db.commit()
    return {"status": "ok"}
