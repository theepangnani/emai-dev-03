"""Service for parsing uploaded .ics files and creating tasks."""

import logging
from datetime import datetime, date, time, timezone
from typing import Optional

from icalendar import Calendar
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.user import User

logger = logging.getLogger(__name__)


def _to_datetime(dt_val) -> datetime:
    """Convert an icalendar date/datetime to a Python datetime (UTC)."""
    if hasattr(dt_val, "dt"):
        dt_val = dt_val.dt
    if not isinstance(dt_val, datetime):
        return datetime.combine(dt_val, time.min, tzinfo=timezone.utc)
    if dt_val.tzinfo is None:
        return dt_val.replace(tzinfo=timezone.utc)
    return dt_val


def parse_ics_file(content: bytes) -> list[dict]:
    """Parse an .ics file and return a list of event dicts.

    Each dict has: summary, dtstart, dtend, description, location.
    Raises ValueError on parse errors.
    """
    try:
        cal = Calendar.from_ical(content)
    except Exception as exc:
        raise ValueError(f"Invalid ICS file: {exc}") from exc

    events: list[dict] = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        dtstart = component.get("DTSTART")
        if not dtstart:
            continue

        summary = str(component.get("SUMMARY", "")).strip()
        if not summary:
            summary = "Untitled Event"

        start_dt = _to_datetime(dtstart)
        dtend = component.get("DTEND")
        end_dt = _to_datetime(dtend) if dtend else None

        description = str(component.get("DESCRIPTION", "")).strip() or None
        location = str(component.get("LOCATION", "")).strip() or None

        events.append({
            "summary": summary[:200],  # Match task title max length
            "dtstart": start_dt,
            "dtend": end_dt,
            "description": description[:5000] if description else None,
            "location": location,
        })

    return events


def import_events_as_tasks(
    db: Session,
    user: User,
    events: list[dict],
    selected_indices: Optional[list[int]] = None,
) -> dict:
    """Create tasks from parsed ICS events, skipping duplicates.

    Args:
        db: Database session
        user: The user creating the tasks
        events: Parsed event dicts from parse_ics_file()
        selected_indices: If provided, only import events at these indices.
                          If None, import all events.

    Returns:
        dict with created_count, skipped_count, errors
    """
    created_count = 0
    skipped_count = 0
    errors: list[str] = []

    if selected_indices is not None:
        to_import = [(i, events[i]) for i in selected_indices if 0 <= i < len(events)]
    else:
        to_import = list(enumerate(events))

    for idx, event in to_import:
        summary = event["summary"]
        dtstart = event["dtstart"]

        try:
            # Dedup: check if a task with the same title and due date already exists
            existing = (
                db.query(Task)
                .filter(
                    Task.created_by_user_id == user.id,
                    Task.title == summary,
                    Task.due_date == dtstart,
                )
                .first()
            )
            if existing:
                skipped_count += 1
                continue

            # Build description from event details
            desc_parts = []
            if event.get("description"):
                desc_parts.append(event["description"])
            if event.get("location"):
                desc_parts.append(f"Location: {event['location']}")
            if event.get("dtend"):
                desc_parts.append(f"End: {event['dtend'].isoformat()}")
            description = "\n".join(desc_parts) if desc_parts else None

            task = Task(
                created_by_user_id=user.id,
                parent_id=user.id,
                title=summary,
                description=description,
                due_date=dtstart,
                priority="medium",
                category="calendar-import",
            )
            db.add(task)
            created_count += 1
        except Exception as exc:
            logger.warning("Failed to import event %d (%s): %s", idx, summary, exc)
            errors.append(f"Event '{summary}': {str(exc)}")

    if created_count > 0:
        db.commit()

    return {
        "created_count": created_count,
        "skipped_count": skipped_count,
        "errors": errors,
    }
