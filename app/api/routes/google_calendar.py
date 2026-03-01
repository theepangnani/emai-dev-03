"""Google Calendar integration routes.

Endpoints:
  GET  /api/google/calendar/status      — Check if user has calendar scope
  POST /api/google/calendar/connect     — Start OAuth flow to grant calendar scope
  POST /api/google/calendar/sync        — Bulk-sync tasks with due dates to Calendar
  DELETE /api/google/calendar/disconnect — Stop syncing (remove calendar_scope preference)
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.user import User
from app.models.task import Task
from app.api.deps import get_current_user
from app.services.google_calendar import (
    CALENDAR_SCOPE,
    sync_task_to_calendar,
    delete_task_from_calendar,
)
from app.services.google_classroom import get_calendar_auth_url
from app.api.routes.google_classroom import _create_oauth_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google/calendar", tags=["Google Calendar"])


@router.get("/status")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def calendar_status(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Check if the user has connected Google and granted calendar scope."""
    connected = bool(current_user.google_access_token)
    scope_granted = current_user.has_google_scope(CALENDAR_SCOPE)
    return {
        "connected": connected,
        "scope_granted": scope_granted,
    }


@router.post("/connect")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def calendar_connect(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Return an OAuth URL that grants the calendar.events scope.

    The user is redirected through Google consent; the existing /api/google/callback
    handler processes the tokens and stores the new scope.  On success it redirects to
    /dashboard?calendar_connected=true.
    """
    state = _create_oauth_state(purpose="calendar_connect", user_id=current_user.id)
    authorization_url, _ = get_calendar_auth_url(state)
    return {"authorization_url": authorization_url}


@router.post("/sync")
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def calendar_sync(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bulk-sync all of the user's tasks (that have a due date) to Google Calendar.

    Skips tasks that have already been synced (google_calendar_event_id is set).
    Returns the count of events successfully synced in this call.
    """
    if not current_user.has_google_scope(CALENDAR_SCOPE):
        return {"synced": 0, "message": "Google Calendar not connected. Please connect first."}

    # Fetch tasks created by the user with a due date
    tasks = (
        db.query(Task)
        .filter(
            Task.created_by_user_id == current_user.id,
            Task.due_date.isnot(None),
            Task.archived_at.is_(None),
        )
        .all()
    )

    synced_count = 0
    for task in tasks:
        try:
            event_id = sync_task_to_calendar(current_user, task)
            if event_id and event_id != task.google_calendar_event_id:
                task.google_calendar_event_id = event_id
                synced_count += 1
            elif event_id:
                # Event already existed and was updated
                synced_count += 1
        except Exception as exc:
            logger.warning("Error syncing task %s to calendar: %s", task.id, exc)

    if synced_count:
        try:
            db.commit()
        except Exception as exc:
            logger.warning("Failed to persist calendar event IDs: %s", exc)
            db.rollback()

    return {
        "synced": synced_count,
        "message": f"Synced {synced_count} task{'s' if synced_count != 1 else ''} to Google Calendar",
    }


@router.delete("/disconnect")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def calendar_disconnect(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stop Google Calendar sync for this user.

    Removes the calendar.events scope from google_granted_scopes so future
    task CRUD operations will skip calendar sync.  Does NOT delete existing
    calendar events (the user may want to keep them) and does NOT revoke the
    full Google token.
    """
    if current_user.google_granted_scopes:
        scopes = [
            s for s in current_user.google_granted_scopes.split(",")
            if s and s != CALENDAR_SCOPE
        ]
        current_user.google_granted_scopes = ",".join(sorted(scopes)) if scopes else None
        db.commit()

    return {"message": "Google Calendar sync disconnected"}
