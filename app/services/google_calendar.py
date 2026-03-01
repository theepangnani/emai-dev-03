"""Google Calendar integration service.

Provides helpers to sync tasks and assignments to a user's Google Calendar.
All public functions are safe to call in a fire-and-forget manner — they
catch and log errors instead of raising, so calendar failures never break
the primary task/assignment CRUD flow.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import google.auth.exceptions
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from app.core.config import settings

logger = logging.getLogger(__name__)

CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"


# ── Credential helpers ────────────────────────────────────────────────────

def _build_credentials(user) -> Credentials:
    """Construct a Credentials object from the user's stored tokens."""
    return Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )


def get_calendar_service(user):
    """Build a Google Calendar API service for the given user.

    Proactively refreshes the access token when a refresh token is available.
    Returns the service object, or None if the user has not granted calendar
    scope or if the token refresh fails.
    """
    if not user.has_google_scope(CALENDAR_SCOPE):
        return None

    if not user.google_access_token:
        return None

    creds = _build_credentials(user)

    if creds.refresh_token:
        try:
            creds.refresh(Request())
        except google.auth.exceptions.RefreshError as exc:
            logger.warning("Google token refresh failed for user %s: %s", user.id, exc)
            return None
        except Exception as exc:
            logger.warning("Unexpected error refreshing Google token for user %s: %s", user.id, exc)
            # Fall through — use the existing token as-is

    try:
        return build("calendar", "v3", credentials=creds)
    except Exception as exc:
        logger.warning("Failed to build Google Calendar service for user %s: %s", user.id, exc)
        return None


# ── Event body builders ───────────────────────────────────────────────────

def _due_date_to_event_date(due_date) -> dict:
    """Convert a due_date (datetime or date) to a Google Calendar date/dateTime dict.

    Google Calendar uses:
    - {"date": "YYYY-MM-DD"} for all-day events
    - {"dateTime": "<ISO string>", "timeZone": "UTC"} for timed events
    """
    if due_date is None:
        # Fallback: today, all-day
        today = date.today().isoformat()
        return {"date": today}

    if isinstance(due_date, datetime):
        # If the datetime has no time component (midnight UTC), treat as all-day
        if due_date.hour == 0 and due_date.minute == 0 and due_date.second == 0:
            return {"date": due_date.date().isoformat()}
        # Timed event
        iso = due_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {"dateTime": iso, "timeZone": "UTC"}

    # Plain date object
    return {"date": due_date.isoformat() if hasattr(due_date, "isoformat") else str(due_date)}


def _build_task_event_body(task) -> dict:
    """Build a Google Calendar event body for a task."""
    date_spec = _due_date_to_event_date(task.due_date)
    event = {
        "summary": task.title,
        "description": task.description or "",
        "start": date_spec,
        "end": date_spec,  # same as start for all-day; Google accepts this
    }
    return event


def _build_assignment_event_body(assignment) -> dict:
    """Build a Google Calendar event body for an assignment."""
    date_spec = _due_date_to_event_date(assignment.due_date)
    description_parts = []
    if assignment.description:
        description_parts.append(assignment.description)
    event = {
        "summary": f"Assignment due: {assignment.title}",
        "description": "\n".join(description_parts),
        "start": date_spec,
        "end": date_spec,
    }
    return event


# ── Public sync helpers ───────────────────────────────────────────────────

def sync_task_to_calendar(user, task) -> str | None:
    """Create or update a Google Calendar event for a task.

    Returns the Google Calendar event ID on success, or None if the user
    hasn't granted calendar scope, or if the API call fails.
    """
    if not task.due_date:
        return None

    service = get_calendar_service(user)
    if service is None:
        return None

    event_body = _build_task_event_body(task)

    try:
        existing_event_id = getattr(task, "google_calendar_event_id", None)

        if existing_event_id:
            # Update existing event
            result = (
                service.events()
                .update(calendarId="primary", eventId=existing_event_id, body=event_body)
                .execute()
            )
            logger.debug("Updated Google Calendar event %s for task %s", result["id"], task.id)
            return result["id"]
        else:
            # Create new event
            result = (
                service.events()
                .insert(calendarId="primary", body=event_body)
                .execute()
            )
            logger.debug("Created Google Calendar event %s for task %s", result["id"], task.id)
            return result["id"]

    except google.auth.exceptions.RefreshError as exc:
        logger.warning("Token refresh error syncing task %s to calendar: %s", task.id, exc)
        return None
    except Exception as exc:
        logger.warning("Failed to sync task %s to Google Calendar: %s", task.id, exc)
        return None


def delete_task_from_calendar(user, google_event_id: str) -> None:
    """Delete a Google Calendar event for a task.

    Silently ignores errors (e.g. event already deleted, scope missing).
    """
    if not google_event_id:
        return

    service = get_calendar_service(user)
    if service is None:
        return

    try:
        service.events().delete(calendarId="primary", eventId=google_event_id).execute()
        logger.debug("Deleted Google Calendar event %s", google_event_id)
    except google.auth.exceptions.RefreshError as exc:
        logger.warning("Token refresh error deleting calendar event %s: %s", google_event_id, exc)
    except Exception as exc:
        logger.warning("Failed to delete Google Calendar event %s: %s", google_event_id, exc)


def sync_assignment_to_calendar(user, assignment) -> str | None:
    """Create or update a Google Calendar event for an assignment due date.

    Returns the Google Calendar event ID on success, or None on failure.
    """
    if not assignment.due_date:
        return None

    service = get_calendar_service(user)
    if service is None:
        return None

    event_body = _build_assignment_event_body(assignment)

    try:
        existing_event_id = getattr(assignment, "google_calendar_event_id", None)

        if existing_event_id:
            result = (
                service.events()
                .update(calendarId="primary", eventId=existing_event_id, body=event_body)
                .execute()
            )
            logger.debug("Updated Google Calendar event %s for assignment %s", result["id"], assignment.id)
            return result["id"]
        else:
            result = (
                service.events()
                .insert(calendarId="primary", body=event_body)
                .execute()
            )
            logger.debug("Created Google Calendar event %s for assignment %s", result["id"], assignment.id)
            return result["id"]

    except google.auth.exceptions.RefreshError as exc:
        logger.warning("Token refresh error syncing assignment %s to calendar: %s", assignment.id, exc)
        return None
    except Exception as exc:
        logger.warning("Failed to sync assignment %s to Google Calendar: %s", assignment.id, exc)
        return None
