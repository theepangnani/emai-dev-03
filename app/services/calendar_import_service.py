import logging
from datetime import datetime, timezone

import httpx
from icalendar import Calendar
from sqlalchemy.orm import Session

from app.models.calendar_feed import CalendarFeed
from app.models.calendar_event import CalendarEvent

logger = logging.getLogger(__name__)


def _to_datetime(dt_val) -> datetime:
    """Convert an icalendar date/datetime to a Python datetime."""
    if hasattr(dt_val, "dt"):
        dt_val = dt_val.dt
    # date (all-day) -> datetime at midnight UTC
    if not isinstance(dt_val, datetime):
        from datetime import date, time
        return datetime.combine(dt_val, time.min, tzinfo=timezone.utc)
    # naive datetime -> assume UTC
    if dt_val.tzinfo is None:
        return dt_val.replace(tzinfo=timezone.utc)
    return dt_val


def _is_all_day(dtstart) -> bool:
    """Check if a DTSTART represents an all-day event."""
    if hasattr(dtstart, "dt"):
        dt_val = dtstart.dt
    else:
        dt_val = dtstart
    from datetime import date
    return isinstance(dt_val, date) and not isinstance(dt_val, datetime)


async def fetch_and_parse_ics(url: str) -> tuple[str | None, list[dict]]:
    """Fetch an ICS URL and return (calendar_name, list_of_event_dicts).

    Raises ValueError on HTTP or parse errors.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise ValueError(f"Failed to fetch calendar: HTTP {resp.status_code}")

    content = resp.content
    try:
        cal = Calendar.from_ical(content)
    except Exception as exc:
        raise ValueError(f"Invalid ICS data: {exc}") from exc

    cal_name = str(cal.get("X-WR-CALNAME", "")) or None
    events: list[dict] = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue
        uid = str(component.get("UID", ""))
        if not uid:
            continue
        dtstart = component.get("DTSTART")
        if not dtstart:
            continue

        all_day = _is_all_day(dtstart)
        start_dt = _to_datetime(dtstart)
        dtend = component.get("DTEND")
        end_dt = _to_datetime(dtend) if dtend else None

        events.append({
            "uid": uid,
            "title": str(component.get("SUMMARY", "Untitled")),
            "description": str(component.get("DESCRIPTION", "")) or None,
            "start_date": start_dt,
            "end_date": end_dt,
            "all_day": all_day,
            "location": str(component.get("LOCATION", "")) or None,
        })

    return cal_name, events


async def sync_calendar_feed(db: Session, feed: CalendarFeed) -> int:
    """Sync a calendar feed: fetch, upsert events, remove stale ones.

    Returns the number of events after sync.
    """
    cal_name, parsed_events = await fetch_and_parse_ics(feed.url)

    if cal_name and not feed.name:
        feed.name = cal_name

    # Build set of UIDs from feed
    incoming_uids = {e["uid"] for e in parsed_events}

    # Existing events for this feed
    existing = db.query(CalendarEvent).filter(CalendarEvent.feed_id == feed.id).all()
    existing_by_uid = {e.uid: e for e in existing}

    # Upsert
    for evt_data in parsed_events:
        uid = evt_data["uid"]
        if uid in existing_by_uid:
            existing_evt = existing_by_uid[uid]
            for key, val in evt_data.items():
                setattr(existing_evt, key, val)
        else:
            new_evt = CalendarEvent(
                feed_id=feed.id,
                user_id=feed.user_id,
                **evt_data,
            )
            db.add(new_evt)

    # Delete events no longer in feed
    for uid, evt in existing_by_uid.items():
        if uid not in incoming_uids:
            db.delete(evt)

    feed.last_synced = datetime.now(timezone.utc)
    feed.event_count = len(parsed_events)
    db.commit()

    return len(parsed_events)
