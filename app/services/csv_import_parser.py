"""CSV template import parser for manual classroom data entry.

Provides downloadable CSV templates and flexible parsing with column name normalization.
Follows the same flexible-mapping pattern as teachassist_parser.py.
"""
import csv
import io
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Flexible column name mapping (lowercase key -> canonical field)
# ---------------------------------------------------------------------------
_COLUMN_MAP: dict[str, str] = {
    # Course columns
    "course": "course_name",
    "course name": "course_name",
    "class": "course_name",
    "class name": "course_name",
    "course_name": "course_name",
    # Assignment columns
    "assignment": "title",
    "assignment title": "title",
    "title": "title",
    "name": "title",
    "description": "description",
    "details": "description",
    "desc": "description",
    "due": "due_date",
    "due date": "due_date",
    "deadline": "due_date",
    "date due": "due_date",
    "due_date": "due_date",
    "points": "max_points",
    "total points": "max_points",
    "max points": "max_points",
    "max": "max_points",
    "max_points": "max_points",
    "status": "status",
    "state": "status",
    # Material columns
    "material": "title",
    "material title": "title",
    "resource": "title",
    "type": "type",
    "material type": "type",
    "content type": "type",
    "url": "url",
    "link": "url",
    "reference": "url",
    # Grade columns
    "score": "score",
    "mark": "score",
    "grade": "score",
    "my grade": "score",
    "max score": "max_score",
    "out of": "max_score",
    "total": "max_score",
    "max_score": "max_score",
}

# ---------------------------------------------------------------------------
# CSV templates
# ---------------------------------------------------------------------------
_TEMPLATES: dict[str, str] = {
    "assignments": (
        "Course Name,Assignment Title,Description,Due Date,Points,Status\n"
        "Math 101,Chapter 5 Homework,Complete problems 1-20,2026-04-15,100,active\n"
        "English 201,Essay Draft,Write first draft of persuasive essay,2026-04-18,50,active\n"
        "Science 301,Lab Report,Photosynthesis experiment write-up,2026-04-20,75,active\n"
    ),
    "materials": (
        "Course Name,Material Title,Description,Type,URL\n"
        "Math 101,Textbook Chapter 5,Algebra fundamentals,document,https://example.com/ch5.pdf\n"
        "English 201,MLA Style Guide,Formatting reference for essays,link,https://example.com/mla\n"
        "Science 301,Lab Safety Video,Required viewing before lab,video,https://example.com/safety.mp4\n"
    ),
    "grades": (
        "Course Name,Assignment Title,Score,Max Score\n"
        "Math 101,Chapter 4 Quiz,85,100\n"
        "English 201,Midterm Essay,42,50\n"
        "Science 301,Lab Report 1,68,75\n"
    ),
}


def get_csv_template(template_type: str) -> str:
    """Return CSV string content for the given template type.

    Args:
        template_type: One of ``"assignments"``, ``"materials"``, or ``"grades"``.

    Returns:
        A CSV string with header row and example data rows.

    Raises:
        ValueError: If *template_type* is not recognised.
    """
    template = _TEMPLATES.get(template_type)
    if template is None:
        valid = ", ".join(sorted(_TEMPLATES))
        raise ValueError(
            f"Unknown template type '{template_type}'. Valid types: {valid}"
        )
    return template


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_header(header: str) -> str | None:
    """Normalise a raw CSV header to its canonical field name.

    The header is lowercased, stripped of leading/trailing whitespace, and
    looked up in :data:`_COLUMN_MAP`.  Returns the canonical field name, or
    ``None`` if no mapping exists.
    """
    key = header.strip().lower()
    return _COLUMN_MAP.get(key)


# Date formats to attempt, in order of preference
_DATE_FORMATS = [
    "%Y-%m-%d",       # 2026-04-15
    "%m/%d/%Y",       # 04/15/2026
    "%d/%m/%Y",       # 15/04/2026
    "%B %d, %Y",      # April 15, 2026
    "%b %d, %Y",      # Apr 15, 2026
    "%Y/%m/%d",       # 2026/04/15
    "%m-%d-%Y",       # 04-15-2026
    "%d-%m-%Y",       # 15-04-2026
    "%B %d %Y",       # April 15 2026 (no comma)
    "%b %d %Y",       # Apr 15 2026
]


def _parse_date_flexible(date_str: str) -> str | None:
    """Attempt to parse *date_str* with multiple common date formats.

    Returns the date as an ISO ``YYYY-MM-DD`` string, or ``None`` if no
    format matches.
    """
    if not date_str:
        return None

    cleaned = date_str.strip()
    if not cleaned:
        return None

    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    logger.warning("Could not parse date '%s' with any known format", date_str)
    return None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_csv_import(content: bytes | str, template_type: str) -> dict[str, Any]:
    """Parse CSV content into a standardised classroom data dict.

    The parser normalises column headers using :data:`_COLUMN_MAP` (case-
    insensitive, stripped) and groups records by course name.

    Args:
        content: Raw CSV bytes or string.
        template_type: One of ``"assignments"``, ``"materials"``, or
            ``"grades"``.  Determines which fields are extracted from
            each row.

    Returns:
        A dict with the keys ``courses``, ``assignments``, ``materials``,
        ``announcements``, and ``grades``.

    Raises:
        ValueError: If the CSV has no header row or *template_type* is
            invalid.
    """
    if template_type not in ("assignments", "materials", "grades"):
        raise ValueError(
            f"Unknown template_type '{template_type}'. "
            "Valid types: assignments, materials, grades"
        )

    # Decode bytes to text -------------------------------------------------
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8-sig")  # handle BOM
        except UnicodeDecodeError:
            text = content.decode("latin-1")
    else:
        text = content

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV file has no header row")

    # Build normalised header -> canonical field mapping --------------------
    header_map: dict[str, str] = {}
    for raw_header in reader.fieldnames:
        canonical = _normalize_header(raw_header)
        if canonical:
            header_map[raw_header] = canonical
        else:
            logger.warning(
                "Unmapped CSV column '%s' — skipping", raw_header
            )

    # Track unique courses -------------------------------------------------
    courses_seen: dict[str, dict[str, Any]] = {}
    assignments: list[dict[str, Any]] = []
    materials: list[dict[str, Any]] = []
    grades: list[dict[str, Any]] = []

    for row_num, raw_row in enumerate(reader, start=2):
        # Map raw columns to canonical fields
        row: dict[str, Any] = {}
        for raw_col, canonical in header_map.items():
            value = (raw_row.get(raw_col) or "").strip()
            if value:
                row[canonical] = value

        # Skip completely empty rows
        if not row:
            continue

        # Extract course name and register it
        course_name = row.get("course_name")
        if course_name and course_name not in courses_seen:
            courses_seen[course_name] = {
                "name": course_name,
                "teacher_name": None,
                "section": None,
            }

        # Build record based on template type
        if template_type == "assignments":
            title = row.get("title")
            if not title:
                logger.debug(
                    "Row %d: skipping assignment row with no title", row_num
                )
                continue

            # Parse max_points as number
            max_points: int | None = None
            raw_points = row.get("max_points")
            if raw_points:
                try:
                    max_points = int(float(raw_points))
                except (ValueError, TypeError):
                    logger.debug(
                        "Row %d: invalid max_points '%s'", row_num, raw_points
                    )

            assignments.append({
                "course_name": course_name,
                "title": title,
                "description": row.get("description"),
                "due_date": _parse_date_flexible(row.get("due_date", "")),
                "max_points": max_points,
                "status": row.get("status", "active"),
            })

        elif template_type == "materials":
            title = row.get("title")
            if not title:
                logger.debug(
                    "Row %d: skipping material row with no title", row_num
                )
                continue

            materials.append({
                "course_name": course_name,
                "title": title,
                "description": row.get("description"),
                "type": row.get("type", "document"),
                "url": row.get("url"),
            })

        elif template_type == "grades":
            title = row.get("title")
            if not title:
                logger.debug(
                    "Row %d: skipping grade row with no title", row_num
                )
                continue

            # Parse numeric score / max_score
            score: float | None = None
            max_score: float | None = None

            raw_score = row.get("score")
            if raw_score:
                try:
                    score = float(raw_score)
                except (ValueError, TypeError):
                    logger.debug(
                        "Row %d: invalid score '%s'", row_num, raw_score
                    )

            raw_max = row.get("max_score")
            if raw_max:
                try:
                    max_score = float(raw_max)
                except (ValueError, TypeError):
                    logger.debug(
                        "Row %d: invalid max_score '%s'", row_num, raw_max
                    )

            grades.append({
                "course_name": course_name,
                "assignment_title": title,
                "score": score,
                "max_score": max_score,
            })

    courses_list = list(courses_seen.values())

    logger.info(
        "CSV import (%s): parsed %d course(s), %d assignment(s), "
        "%d material(s), %d grade(s)",
        template_type,
        len(courses_list),
        len(assignments),
        len(materials),
        len(grades),
    )

    return {
        "courses": courses_list,
        "assignments": assignments,
        "materials": materials,
        "announcements": [],
        "grades": grades,
    }
