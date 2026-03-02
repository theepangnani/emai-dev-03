"""Notification preference endpoints (#966).

GET  /api/notifications/preferences          — get current user's preferences
PUT  /api/notifications/preferences          — upsert preferences
GET  /api/notifications/digest/preview       — preview what today's digest would contain
"""
import logging
from datetime import datetime, timezone, date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.database import get_db
from app.models.user import User
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.schemas.notification import (
    AdvancedNotificationPreferences,
    AdvancedNotificationPreferencesResponse,
    NotificationResponse,
)
from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notification Preferences"])


def _get_or_create_preferences(db: Session, user_id: int) -> NotificationPreference:
    """Return existing preferences or create defaults."""
    prefs = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == user_id
    ).first()
    if prefs is None:
        prefs = NotificationPreference(user_id=user_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


@router.get("/preferences", response_model=AdvancedNotificationPreferencesResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_preferences(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's advanced notification preferences.
    Creates default preferences if none exist yet.
    """
    prefs = _get_or_create_preferences(db, current_user.id)
    return prefs


@router.put("/preferences", response_model=AdvancedNotificationPreferencesResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_preferences(
    request: Request,
    data: AdvancedNotificationPreferences,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upsert advanced notification preferences (full replace of all toggles)."""
    prefs = _get_or_create_preferences(db, current_user.id)

    prefs.in_app_assignments = data.in_app_assignments
    prefs.in_app_messages = data.in_app_messages
    prefs.in_app_tasks = data.in_app_tasks
    prefs.in_app_system = data.in_app_system
    prefs.in_app_reminders = data.in_app_reminders

    prefs.email_assignments = data.email_assignments
    prefs.email_messages = data.email_messages
    prefs.email_tasks = data.email_tasks
    prefs.email_reminders = data.email_reminders

    prefs.digest_mode = data.digest_mode
    prefs.digest_hour = data.digest_hour
    prefs.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(prefs)

    logger.info(
        f"Updated advanced notification preferences for user {current_user.id} | "
        f"digest_mode={data.digest_mode} digest_hour={data.digest_hour}"
    )
    return prefs


@router.get("/digest/preview", response_model=list[NotificationResponse])
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def digest_preview(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the unread notifications that would be included in today's digest.

    Ordered newest-first, limited to 100 entries.
    """
    prefs = _get_or_create_preferences(db, current_user.id)

    # Start of today (UTC)
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

    # Determine cutoff: either start of today OR last digest sent time
    if prefs.last_digest_sent_at:
        last_sent = prefs.last_digest_sent_at
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        cutoff = max(last_sent, today_start)
    else:
        cutoff = today_start

    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.read == False,  # noqa: E712
            Notification.created_at >= cutoff,
        )
        .order_by(desc(Notification.created_at))
        .limit(100)
        .all()
    )
    return notifications
