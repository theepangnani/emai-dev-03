"""Smart Reminders API — preferences, logs, manual trigger, stats.

Routes:
  GET  /api/reminders/preferences   — fetch current user's reminder preferences
  PUT  /api/reminders/preferences   — update preferences
  GET  /api/reminders/logs          — last 50 reminder logs for the current user
  POST /api/reminders/test          — admin: manually trigger a full reminder run
  GET  /api/reminders/stats         — admin: sent-today counts broken down by urgency
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.database import get_db
from app.models.smart_reminder import ReminderLog, ReminderPreference, ReminderUrgency
from app.models.user import User, UserRole

router = APIRouter(prefix="/reminders", tags=["smart-reminders"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class ReminderPreferenceOut(BaseModel):
    user_id: int
    remind_3_days: bool
    remind_1_day: bool
    remind_3_hours: bool
    remind_overdue: bool
    ai_personalized_messages: bool
    parent_escalation_hours: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReminderPreferenceUpdate(BaseModel):
    remind_3_days: Optional[bool] = None
    remind_1_day: Optional[bool] = None
    remind_3_hours: Optional[bool] = None
    remind_overdue: Optional[bool] = None
    ai_personalized_messages: Optional[bool] = None
    parent_escalation_hours: Optional[int] = Field(None, ge=0, le=168)


class ReminderLogOut(BaseModel):
    id: int
    user_id: int
    assignment_id: Optional[int] = None
    urgency: ReminderUrgency
    message: str
    sent_at: datetime
    channel: str
    priority_score: Optional[float] = None

    class Config:
        from_attributes = True


class ReminderStatsOut(BaseModel):
    sent_today: int
    by_urgency: dict[str, int]
    total_all_time: int


class TriggerResultOut(BaseModel):
    sent: int
    skipped: int
    errors: int
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_preferences(db: Session, user_id: int) -> ReminderPreference:
    """Return existing ReminderPreference or create defaults on first access."""
    prefs = db.query(ReminderPreference).filter(ReminderPreference.user_id == user_id).first()
    if not prefs:
        prefs = ReminderPreference(user_id=user_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/preferences", response_model=ReminderPreferenceOut)
def get_reminder_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderPreferenceOut:
    """Return the current user's reminder preferences (creates defaults if first visit)."""
    prefs = _get_or_create_preferences(db, current_user.id)
    return prefs


@router.put("/preferences", response_model=ReminderPreferenceOut)
def update_reminder_preferences(
    payload: ReminderPreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReminderPreferenceOut:
    """Update reminder preferences for the current user. Only provided fields are changed."""
    prefs = _get_or_create_preferences(db, current_user.id)

    if payload.remind_3_days is not None:
        prefs.remind_3_days = payload.remind_3_days
    if payload.remind_1_day is not None:
        prefs.remind_1_day = payload.remind_1_day
    if payload.remind_3_hours is not None:
        prefs.remind_3_hours = payload.remind_3_hours
    if payload.remind_overdue is not None:
        prefs.remind_overdue = payload.remind_overdue
    if payload.ai_personalized_messages is not None:
        prefs.ai_personalized_messages = payload.ai_personalized_messages
    if payload.parent_escalation_hours is not None:
        prefs.parent_escalation_hours = payload.parent_escalation_hours

    db.commit()
    db.refresh(prefs)
    logger.info(f"Reminder preferences updated | user={current_user.id}")
    return prefs


@router.get("/logs", response_model=list[ReminderLogOut])
def get_reminder_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReminderLogOut]:
    """Return the most recent reminder log entries for the current user (max 50)."""
    limit = min(limit, 50)
    logs = (
        db.query(ReminderLog)
        .filter(ReminderLog.user_id == current_user.id)
        .order_by(ReminderLog.sent_at.desc())
        .limit(limit)
        .all()
    )
    return logs


@router.post("/test", response_model=TriggerResultOut)
def trigger_reminder_run(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> TriggerResultOut:
    """Admin-only: manually trigger a full smart reminder run immediately."""
    from app.services.smart_reminders import SmartReminderService

    logger.info(f"Manual reminder trigger by admin | user={current_user.id}")
    service = SmartReminderService()
    result = service.run_smart_reminders(db)
    return TriggerResultOut(
        sent=result["sent"],
        skipped=result["skipped"],
        errors=result["errors"],
        message=f"Reminder run complete: {result['sent']} sent, {result['errors']} errors.",
    )


@router.get("/stats", response_model=ReminderStatsOut)
def get_reminder_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> ReminderStatsOut:
    """Admin-only: return reminder statistics (sent today, breakdown by urgency, total)."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_all_time = db.query(ReminderLog).count()

    today_logs = (
        db.query(ReminderLog)
        .filter(ReminderLog.sent_at >= today_start)
        .all()
    )

    by_urgency: dict[str, int] = {u.value: 0 for u in ReminderUrgency}
    for log in today_logs:
        urgency_key = log.urgency.value if log.urgency else "unknown"
        by_urgency[urgency_key] = by_urgency.get(urgency_key, 0) + 1

    return ReminderStatsOut(
        sent_today=len(today_logs),
        by_urgency=by_urgency,
        total_all_time=total_all_time,
    )
