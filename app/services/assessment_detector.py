"""Detect upcoming assessments from document text using regex patterns."""
import re
from datetime import date, datetime, timedelta

# Keywords that indicate an assessment event
_KEYWORDS = r"(?:test|exam|quiz|midterm|final|assessment|due\s+date|lab|project|presentation)"

# Date patterns
_MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_DAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3,
    "fri": 4, "sat": 5, "sun": 6,
}

# Regex: "Month Day" or "Month Day, Year"
_MONTH_DAY_RE = re.compile(
    r"\b(" + "|".join(_MONTH_NAMES.keys()) + r")\s+(\d{1,2})(?:\s*,?\s*(\d{4}))?\b",
    re.IGNORECASE,
)

# Regex: ISO-style dates YYYY-MM-DD or YYYY/MM/DD
_ISO_DATE_RE = re.compile(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b")

# Regex: MM/DD/YYYY or MM-DD-YYYY
_US_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")

# Regex: day name (e.g., "Friday")
_DAY_NAME_RE = re.compile(
    r"\b(" + "|".join(_DAY_NAMES.keys()) + r")\b",
    re.IGNORECASE,
)

# Context pattern: keyword near a date
_CONTEXT_RE = re.compile(
    r"(" + _KEYWORDS + r")\s*(?::|\s+on\s+|\s+)\s*",
    re.IGNORECASE,
)


def _resolve_day_name(day_name: str, reference: date | None = None) -> date:
    """Resolve a day name to the next occurrence from the reference date."""
    ref = reference or date.today()
    target_weekday = _DAY_NAMES[day_name.lower()]
    days_ahead = (target_weekday - ref.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7  # next week if today
    return ref + timedelta(days=days_ahead)


def _parse_month_day(match: re.Match, reference: date | None = None) -> date | None:
    """Parse a Month Day[, Year] match into a date."""
    ref = reference or date.today()
    month_str = match.group(1).lower()
    day = int(match.group(2))
    year_str = match.group(3)
    month = _MONTH_NAMES.get(month_str)
    if not month or day < 1 or day > 31:
        return None
    year = int(year_str) if year_str else ref.year
    try:
        d = date(year, month, day)
        # If no year given and date is in the past, assume next year
        if not year_str and d < ref:
            d = date(year + 1, month, day)
        return d
    except ValueError:
        return None


def _infer_event_type(text: str) -> str:
    """Infer the event type from surrounding text."""
    lower = text.lower()
    if "exam" in lower or "final" in lower:
        return "exam"
    if "quiz" in lower:
        return "quiz"
    if "midterm" in lower:
        return "midterm"
    if "lab" in lower:
        return "lab"
    if "project" in lower or "presentation" in lower:
        return "assignment"
    if "due" in lower:
        return "assignment"
    return "test"


def detect_assessments(
    text: str,
    filename: str = "",
    course_id: int | None = None,
    reference_date: date | None = None,
) -> list[dict]:
    """Detect assessment dates from document text.

    Returns a list of dicts with keys:
        event_type, event_title, event_date, source
    """
    if not text:
        return []

    ref = reference_date or date.today()
    results: list[dict] = []
    seen: set[tuple[str, date]] = set()

    # Split text into lines for context
    lines = text.split("\n")

    for line in lines:
        line_lower = line.lower()
        # Check if line contains assessment keywords
        has_keyword = bool(re.search(_KEYWORDS, line_lower))
        if not has_keyword:
            continue

        # Try to find dates in this line
        dates_found: list[tuple[date, str]] = []

        # Month Day patterns
        for m in _MONTH_DAY_RE.finditer(line):
            d = _parse_month_day(m, ref)
            if d:
                dates_found.append((d, m.group(0)))

        # ISO dates
        for m in _ISO_DATE_RE.finditer(line):
            try:
                d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                dates_found.append((d, m.group(0)))
            except ValueError:
                pass

        # US dates
        for m in _US_DATE_RE.finditer(line):
            try:
                d = date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
                dates_found.append((d, m.group(0)))
            except ValueError:
                pass

        # Day names (e.g., "quiz Friday")
        for m in _DAY_NAME_RE.finditer(line):
            d = _resolve_day_name(m.group(1), ref)
            dates_found.append((d, m.group(0)))

        event_type = _infer_event_type(line)

        for event_date, date_str in dates_found:
            # Only keep future dates (within 90 days)
            if event_date < ref or event_date > ref + timedelta(days=90):
                continue

            # Build a title from the line context
            title = line.strip()
            if len(title) > 200:
                title = title[:197] + "..."

            key = (title, event_date)
            if key in seen:
                continue
            seen.add(key)

            results.append({
                "event_type": event_type,
                "event_title": title,
                "event_date": event_date,
                "source": "document_parse",
            })

    return results
