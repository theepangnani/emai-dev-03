"""ICS calendar file parser for Google Classroom assignment import.

Google Classroom creates calendar events for assignment due dates. Students can export
their Google Calendar as .ics and import here to get assignment titles + due dates.
"""
import logging
import re
from datetime import datetime, date

logger = logging.getLogger(__name__)


def _extract_classroom_url(description: str) -> str | None:
    """Extract classroom.google.com URL from event description.

    Google Classroom events typically embed a link like:
        https://classroom.google.com/c/ABC123/a/DEF456/details
    """
    if not description:
        return None
    match = re.search(r'https?://classroom\.google\.com\S+', description)
    return match.group(0).rstrip(">.),;'\"") if match else None


def _parse_dtstart(component) -> str | None:
    """Extract the DTSTART value from a VEVENT and return as YYYY-MM-DD string.

    DTSTART can be a datetime or a date object depending on the event type
    (all-day vs timed).
    """
    dt_prop = component.get("dtstart")
    if dt_prop is None:
        return None

    dt_val = dt_prop.dt
    if isinstance(dt_val, datetime):
        return dt_val.strftime("%Y-%m-%d")
    elif isinstance(dt_val, date):
        return dt_val.strftime("%Y-%m-%d")
    else:
        # Fallback: try string conversion
        try:
            return str(dt_val)[:10]
        except Exception:
            return None


def _split_summary(summary: str) -> tuple[str, str]:
    """Split a SUMMARY string into (title, course_name).

    Google Classroom events often use the format:
        "Assignment Title - Course Name"

    If no " - " delimiter is found, returns the full summary as the title
    and "Unknown Course" as the course name.
    """
    if " - " in summary:
        parts = summary.split(" - ", 1)
        title = parts[0].strip()
        course_name = parts[1].strip()
        if title and course_name:
            return title, course_name
    return summary.strip(), "Unknown Course"


def parse_ics_file(content: bytes | str) -> dict:
    """Parse an ICS calendar file and extract Google Classroom events.

    Google Classroom events have patterns:
    - SUMMARY: "Assignment Title" or "Assignment Title - Course Name"
    - DESCRIPTION: often contains classroom.google.com link
    - DTSTART/DTEND: the due date
    - UID: globally unique event ID (for dedup)

    Returns dict matching the standard parsed data format:
    {
        "courses": [{"name": str, "teacher_name": null, "section": null}],
        "assignments": [{"title": str, "description": str|null, "due_date": "YYYY-MM-DD"|null,
                         "max_points": null, "course_name": str|null, "status": null,
                         "uid": str|null}],
        "materials": [],
        "announcements": [],
        "grades": []
    }
    """
    try:
        from icalendar import Calendar
    except ImportError as exc:
        raise ImportError(
            "The 'icalendar' library is required for ICS parsing. "
            "Install it with: pip install icalendar"
        ) from exc

    # Normalise input to string
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
    else:
        text = content

    if not text.strip():
        logger.warning("ICS parser received empty content")
        return {
            "courses": [],
            "assignments": [],
            "materials": [],
            "announcements": [],
            "grades": [],
        }

    # Parse the calendar
    try:
        cal = Calendar.from_ical(text)
    except Exception as exc:
        logger.warning("ICS parse error: %s", exc)
        raise ValueError(f"Invalid ICS file: {exc}") from exc

    # Track unique courses and collect assignments
    course_names: set[str] = set()
    assignments: list[dict] = []
    seen_uids: set[str] = set()

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        # Extract SUMMARY (required for a meaningful event)
        summary_prop = component.get("summary")
        if not summary_prop:
            logger.debug("Skipping VEVENT with no SUMMARY")
            continue
        summary = str(summary_prop).strip()
        if not summary:
            continue

        # UID for deduplication
        uid_prop = component.get("uid")
        uid = str(uid_prop).strip() if uid_prop else None
        if uid and uid in seen_uids:
            logger.debug("Skipping duplicate UID: %s", uid)
            continue
        if uid:
            seen_uids.add(uid)

        # Parse title and course name from summary
        title, course_name = _split_summary(summary)

        # Extract due date from DTSTART
        due_date = _parse_dtstart(component)

        # Extract description and look for Classroom URL
        desc_prop = component.get("description")
        description = str(desc_prop).strip() if desc_prop else None
        if description == "":
            description = None

        classroom_url = _extract_classroom_url(description) if description else None

        # Build a richer description if we found a Classroom URL
        if classroom_url and description:
            # Keep the original description, the URL is embedded in it
            pass
        elif classroom_url:
            description = classroom_url

        # Track the course
        course_names.add(course_name)

        assignment = {
            "title": title,
            "description": description,
            "due_date": due_date,
            "max_points": None,
            "course_name": course_name,
            "status": None,
            "uid": uid,
        }
        assignments.append(assignment)

    # Build unique courses list
    courses = [
        {"name": name, "teacher_name": None, "section": None}
        for name in sorted(course_names)
    ]

    logger.info(
        "ICS parser: extracted %d assignment(s) across %d course(s)",
        len(assignments),
        len(courses),
    )

    return {
        "courses": courses,
        "assignments": assignments,
        "materials": [],
        "announcements": [],
        "grades": [],
    }
