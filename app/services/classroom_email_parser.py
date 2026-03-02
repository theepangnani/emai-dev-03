"""Parser for Google Classroom email notifications.

Google Classroom sends notification emails for:
- New assignments: Subject "[Course Name] New assignment: Title"
- Due reminders: Subject "[Course Name] Work is due tomorrow: Title" or "Work due soon"
- Guardian summaries: Weekly digest with multiple courses/assignments
- Grade posted: Subject "[Course Name] Grade posted for: Title"
- Announcements: Subject "[Course Name] New post from Teacher Name"
- Comments: Subject "[Course Name] New comment on: Title"
"""
import re
import logging
from datetime import datetime, date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known sender patterns
# ---------------------------------------------------------------------------
_CLASSROOM_SENDERS = (
    "@classroom.google.com",
    "noreply@google.com",
    "classroom-noreply@google.com",
)

# ---------------------------------------------------------------------------
# Subject-line regex patterns
# ---------------------------------------------------------------------------
# [CourseName] New assignment: Title
_RE_ASSIGNMENT = re.compile(
    r"^\[(.+?)\]\s+New assignment:\s*(.+)$", re.IGNORECASE
)
# [CourseName] Work is due tomorrow: Title  |  [CourseName] Work due soon: Title
_RE_DUE_REMINDER = re.compile(
    r"^\[(.+?)\]\s+Work\s+(?:is\s+)?due\s+(?:tomorrow|soon|today)(?::\s*(.+))?$",
    re.IGNORECASE,
)
# Guardian summary for [StudentName]  |  Weekly summary for [StudentName]
_RE_GUARDIAN_SUMMARY = re.compile(
    r"^(?:Guardian|Weekly)\s+summary\s+for\s+(.+)$", re.IGNORECASE
)
# [CourseName] Grade posted for: Title
_RE_GRADE = re.compile(
    r"^\[(.+?)\]\s+Grade\s+posted\s+(?:for)?:\s*(.+)$", re.IGNORECASE
)
# [CourseName] New post from Teacher Name
_RE_ANNOUNCEMENT = re.compile(
    r"^\[(.+?)\]\s+New post from\s+(.+)$", re.IGNORECASE
)
# [CourseName] New comment on: Title
_RE_COMMENT = re.compile(
    r"^\[(.+?)\]\s+New comment on:\s*(.+)$", re.IGNORECASE
)

# Body-parsing helpers
_RE_DUE_DATE_LINE = re.compile(
    r"(?:due|due date|deadline)\s*:?\s*(.+)", re.IGNORECASE
)
_RE_POINTS_LINE = re.compile(
    r"(\d+)\s*(?:points?|pts?|marks?)\s*(?:possible)?", re.IGNORECASE
)
_RE_SCORE = re.compile(
    r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", re.IGNORECASE
)
_RE_GUARDIAN_COURSE = re.compile(r"^([A-Z].*?)$", re.MULTILINE)
_RE_GUARDIAN_ASSIGNMENT = re.compile(
    r"^\s+(?:Assignment|Work):\s*(.+?)(?:\s*-\s*(Due .+?|Missing|Turned in|Graded))?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Month name mapping for lightweight date parsing
_MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


# ---------------------------------------------------------------------------
# Standard empty result
# ---------------------------------------------------------------------------

def _empty_result() -> dict:
    """Return the standard empty parsed-data structure."""
    return {
        "email_type": "unknown",
        "courses": [],
        "assignments": [],
        "materials": [],
        "announcements": [],
        "grades": [],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_classroom_email(
    subject: str,
    body_text: str,
    body_html: str | None = None,
    from_email: str = "",
) -> dict:
    """Parse a Google Classroom notification email.

    Main entry point.  Detects the email type from the subject line, then
    dispatches to the appropriate sub-parser.

    Returns a dict with the standard keys:
        email_type, courses, assignments, materials, announcements, grades
    """
    subject = (subject or "").strip()
    body_text = (body_text or "").strip()
    from_email = (from_email or "").strip().lower()

    if not subject and not body_text:
        logger.warning("parse_classroom_email called with empty subject and body")
        return _empty_result()

    email_type = _detect_email_type(subject, from_email)
    logger.info(
        "Classroom email detected | type=%s | subject=%s | from=%s",
        email_type, subject[:80], from_email,
    )

    dispatch = {
        "assignment": _parse_assignment_email,
        "due_reminder": _parse_due_reminder_email,
        "guardian_summary": _parse_guardian_summary,
        "grade": _parse_grade_email,
        "announcement": _parse_announcement_email,
        "comment": _parse_comment_email,
    }

    parser = dispatch.get(email_type)
    if parser:
        try:
            result = parser(subject, body_text)
            result["email_type"] = email_type
            return result
        except Exception:
            logger.exception(
                "Error parsing classroom email | type=%s | subject=%s",
                email_type, subject[:80],
            )
            result = _empty_result()
            result["email_type"] = email_type
            return result

    # Unknown type — return empty with whatever course we can extract
    result = _empty_result()
    result["email_type"] = "unknown"
    course = _extract_course_from_subject(subject)
    if course:
        result["courses"].append({"name": course})
    return result


# ---------------------------------------------------------------------------
# Email type detection
# ---------------------------------------------------------------------------

def _detect_email_type(subject: str, from_email: str) -> str:
    """Determine the Google Classroom email notification type.

    Returns one of:
        "assignment", "due_reminder", "guardian_summary", "grade",
        "announcement", "comment", "unknown"
    """
    if not subject:
        return "unknown"

    # Check subject-line patterns in order of specificity
    if _RE_ASSIGNMENT.search(subject):
        return "assignment"
    if _RE_DUE_REMINDER.search(subject):
        return "due_reminder"
    if _RE_GUARDIAN_SUMMARY.search(subject):
        return "guardian_summary"
    if _RE_GRADE.search(subject):
        return "grade"
    if _RE_ANNOUNCEMENT.search(subject):
        return "announcement"
    if _RE_COMMENT.search(subject):
        return "comment"

    # Fallback: broader keyword checks with sender validation
    subj_lower = subject.lower()
    is_classroom_sender = any(
        from_email.endswith(sender) for sender in _CLASSROOM_SENDERS
    )

    if is_classroom_sender:
        if "new assignment" in subj_lower:
            return "assignment"
        if "due" in subj_lower and "work" in subj_lower:
            return "due_reminder"
        if "summary" in subj_lower:
            return "guardian_summary"
        if "grade" in subj_lower:
            return "grade"
        if "new post" in subj_lower or "announcement" in subj_lower:
            return "announcement"
        if "comment" in subj_lower:
            return "comment"

    return "unknown"


# ---------------------------------------------------------------------------
# Sub-parsers
# ---------------------------------------------------------------------------

def _parse_assignment_email(subject: str, body_text: str) -> dict:
    """Parse a new-assignment notification email.

    Extracts:
    - course_name from [brackets] in subject
    - assignment title after "New assignment:"
    - due date from body text
    - points from body text
    """
    result = _empty_result()

    # Extract from subject
    match = _RE_ASSIGNMENT.search(subject)
    course_name = match.group(1).strip() if match else _extract_course_from_subject(subject)
    assignment_title = match.group(2).strip() if match else _extract_after_colon(subject, "New assignment")

    if course_name:
        result["courses"].append({"name": course_name})

    assignment: dict = {"title": assignment_title or subject}
    if course_name:
        assignment["course_name"] = course_name

    # Look for due date in body
    due_date = _extract_due_date(body_text)
    if due_date:
        assignment["due_date"] = due_date

    # Look for points in body
    points = _extract_points(body_text)
    if points is not None:
        assignment["max_points"] = points

    # Look for description — first non-empty paragraph that isn't metadata
    description = _extract_description(body_text)
    if description:
        assignment["description"] = description

    result["assignments"].append(assignment)
    return result


def _parse_due_reminder_email(subject: str, body_text: str) -> dict:
    """Parse a due-date reminder email.

    Subject patterns:
    - "[CourseName] Work is due tomorrow: Title"
    - "[CourseName] Work due soon: Title"
    """
    result = _empty_result()

    match = _RE_DUE_REMINDER.search(subject)
    course_name = match.group(1).strip() if match else _extract_course_from_subject(subject)
    assignment_title = (match.group(2).strip() if match and match.group(2) else None)

    if course_name:
        result["courses"].append({"name": course_name})

    assignment: dict = {}
    if assignment_title:
        assignment["title"] = assignment_title
    if course_name:
        assignment["course_name"] = course_name

    # Determine urgency from subject
    subj_lower = subject.lower()
    if "tomorrow" in subj_lower:
        assignment["due_date"] = _parse_relative_date("tomorrow")
        assignment["urgency"] = "tomorrow"
    elif "today" in subj_lower:
        assignment["due_date"] = _parse_relative_date("today")
        assignment["urgency"] = "today"
    else:
        assignment["urgency"] = "soon"
        # Try to get a due date from the body
        due_date = _extract_due_date(body_text)
        if due_date:
            assignment["due_date"] = due_date

    # Parse body for additional assignments listed
    body_assignments = _extract_assignments_from_body(body_text)
    if body_assignments:
        for ba in body_assignments:
            if course_name:
                ba.setdefault("course_name", course_name)
            result["assignments"].append(ba)
    elif assignment.get("title"):
        result["assignments"].append(assignment)
    else:
        # Fallback: single unnamed assignment
        assignment["title"] = "Unknown assignment"
        result["assignments"].append(assignment)

    return result


def _parse_guardian_summary(subject: str, body_text: str) -> dict:
    """Parse a guardian / weekly summary email.

    Expected body structure::

        Weekly summary for Student Name

        Course Name 1
          Assignment: Title A - Due Jan 15
          Assignment: Title B - Missing

        Course Name 2
          Assignment: Title C - Turned in

    Extracts multiple courses and their associated assignments with statuses.
    """
    result = _empty_result()

    # Extract student name from subject
    match = _RE_GUARDIAN_SUMMARY.search(subject)
    student_name: str | None = match.group(1).strip() if match else None
    if student_name:
        result["student_name"] = student_name

    if not body_text:
        return result

    # Parse the body line by line
    lines = body_text.splitlines()
    current_course: str | None = None
    seen_courses: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for assignment line (indented, starts with "Assignment:" or "Work:")
        assignment_match = re.match(
            r"^\s{2,}(?:Assignment|Work)\s*:\s*(.+?)(?:\s*-\s*(Due .+?|Missing|Turned in|Graded.*?))?\s*$",
            line,
            re.IGNORECASE,
        )
        if assignment_match and current_course:
            title = assignment_match.group(1).strip()
            status_raw = (assignment_match.group(2) or "").strip()

            assignment: dict = {
                "title": title,
                "course_name": current_course,
            }

            # Parse status
            if status_raw.lower() == "missing":
                assignment["status"] = "missing"
            elif status_raw.lower() == "turned in":
                assignment["status"] = "turned_in"
            elif status_raw.lower().startswith("graded"):
                assignment["status"] = "graded"
                # Try to extract score from "Graded: 85/100"
                score_match = _RE_SCORE.search(status_raw)
                if score_match:
                    assignment["score"] = float(score_match.group(1))
                    assignment["max_score"] = float(score_match.group(2))
            elif status_raw.lower().startswith("due"):
                assignment["status"] = "pending"
                due_text = status_raw[3:].strip()  # Remove "Due" prefix
                due_date = _parse_relative_date(due_text)
                if due_date:
                    assignment["due_date"] = due_date
            else:
                assignment["status"] = "unknown"

            result["assignments"].append(assignment)
            continue

        # Check for a broader assignment-like line (some formats differ)
        broad_match = re.match(
            r"^\s{2,}(.+?)(?:\s*[-\u2013\u2014]\s*(Due .+?|Missing|Turned in|Graded.*?))?\s*$",
            line,
        )
        if broad_match and current_course and not _looks_like_course_name(stripped):
            title = broad_match.group(1).strip()
            status_raw = (broad_match.group(2) or "").strip()
            # Skip lines that are clearly not assignments (too short, look like headers)
            if len(title) > 2 and not title.endswith(":"):
                assignment = {
                    "title": title,
                    "course_name": current_course,
                    "status": _normalise_status(status_raw) if status_raw else "unknown",
                }
                if status_raw.lower().startswith("due"):
                    due_text = status_raw[3:].strip()
                    due_date = _parse_relative_date(due_text)
                    if due_date:
                        assignment["due_date"] = due_date
                result["assignments"].append(assignment)
            continue

        # Otherwise, check if this is a course header line (not indented, no prefix)
        if not line.startswith(" ") and not line.startswith("\t"):
            # Skip the summary title line itself
            if re.match(r"^(?:Guardian|Weekly)\s+summary", stripped, re.IGNORECASE):
                continue
            # Skip generic labels
            if stripped.lower() in ("assignments", "courses", "overview", "---"):
                continue
            # Treat as course name
            if len(stripped) > 1 and stripped not in seen_courses:
                current_course = stripped
                seen_courses.add(stripped)
                result["courses"].append({"name": current_course})

    return result


def _parse_grade_email(subject: str, body_text: str) -> dict:
    """Parse a grade-posted notification email.

    Subject: "[CourseName] Grade posted for: Assignment Title"
    Body may contain the numeric score.
    """
    result = _empty_result()

    match = _RE_GRADE.search(subject)
    course_name = match.group(1).strip() if match else _extract_course_from_subject(subject)
    assignment_title = match.group(2).strip() if match else _extract_after_colon(subject, "Grade posted for")

    if course_name:
        result["courses"].append({"name": course_name})

    grade: dict = {
        "assignment_title": assignment_title or "Unknown",
    }
    if course_name:
        grade["course_name"] = course_name

    # Extract score from body
    score_match = _RE_SCORE.search(body_text)
    if score_match:
        grade["score"] = float(score_match.group(1))
        grade["max_score"] = float(score_match.group(2))
    else:
        # Look for standalone number that could be a percentage or score
        pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", body_text)
        if pct_match:
            grade["score_percentage"] = float(pct_match.group(1))

    # Look for letter grade
    letter_match = re.search(
        r"\b(A\+?|A-|B\+?|B-|C\+?|C-|D\+?|D-|F)\b", body_text
    )
    if letter_match:
        grade["letter_grade"] = letter_match.group(1)

    result["grades"].append(grade)
    return result


def _parse_announcement_email(subject: str, body_text: str) -> dict:
    """Parse an announcement / new-post notification email.

    Subject: "[CourseName] New post from Teacher Name"
    Body contains the announcement text.
    """
    result = _empty_result()

    match = _RE_ANNOUNCEMENT.search(subject)
    course_name = match.group(1).strip() if match else _extract_course_from_subject(subject)
    teacher_name = match.group(2).strip() if match else None

    if course_name:
        result["courses"].append({"name": course_name})

    announcement: dict = {
        "course_name": course_name or "Unknown",
    }
    if teacher_name:
        announcement["teacher_name"] = teacher_name

    # The body IS the announcement content.  Strip common email footer noise.
    content = _strip_email_footer(body_text)
    if content:
        announcement["content"] = content

    result["announcements"].append(announcement)
    return result


def _parse_comment_email(subject: str, body_text: str) -> dict:
    """Parse a comment notification email.

    Subject: "[CourseName] New comment on: Assignment Title"
    Body contains the comment text and commenter.
    """
    result = _empty_result()

    match = _RE_COMMENT.search(subject)
    course_name = match.group(1).strip() if match else _extract_course_from_subject(subject)
    assignment_title = match.group(2).strip() if match else _extract_after_colon(subject, "New comment on")

    if course_name:
        result["courses"].append({"name": course_name})

    announcement: dict = {
        "type": "comment",
        "course_name": course_name or "Unknown",
        "assignment_title": assignment_title or "Unknown",
    }

    # Try to extract commenter name and comment body
    commenter, comment_text = _extract_comment_details(body_text)
    if commenter:
        announcement["commenter"] = commenter
    if comment_text:
        announcement["content"] = comment_text

    result["announcements"].append(announcement)
    return result


# ---------------------------------------------------------------------------
# Shared extraction helpers
# ---------------------------------------------------------------------------

def _extract_course_from_subject(subject: str) -> str | None:
    """Extract the course name from [brackets] in the subject line.

    Returns the text between the first '[' and ']', or None if not found.
    """
    if not subject:
        return None
    match = re.search(r"\[(.+?)\]", subject)
    return match.group(1).strip() if match else None


def _extract_after_colon(subject: str, keyword: str) -> str | None:
    """Extract text after 'keyword:' in the subject, case-insensitive."""
    pattern = re.compile(
        rf"{re.escape(keyword)}\s*:\s*(.+)$", re.IGNORECASE
    )
    match = pattern.search(subject)
    return match.group(1).strip() if match else None


def _parse_relative_date(text: str) -> str | None:
    """Parse a relative or absolute date string into ISO format (YYYY-MM-DD).

    Handles:
    - "tomorrow" -> date.today() + 1
    - "today" -> date.today()
    - "Mon, Jan 15" / "January 15" / "Jan 15, 2026" style dates
    - "2026-01-15" ISO format passthrough
    """
    if not text:
        return None

    text = text.strip().lower()

    # Relative dates
    if text == "tomorrow":
        return (date.today() + timedelta(days=1)).isoformat()
    if text == "today":
        return date.today().isoformat()
    if text == "yesterday":
        return (date.today() - timedelta(days=1)).isoformat()

    # ISO format passthrough
    iso_match = re.match(r"^(\d{4}-\d{2}-\d{2})$", text)
    if iso_match:
        return iso_match.group(1)

    # "Jan 15", "January 15", "Jan 15, 2026", "15 Jan 2026"
    # Pattern 1: Month Day [, Year]
    m = re.match(
        r"^(?:\w+,?\s+)?(\w+)\s+(\d{1,2})(?:,?\s+(\d{4}))?$", text
    )
    if m:
        month_str = m.group(1).lower()
        day = int(m.group(2))
        year = int(m.group(3)) if m.group(3) else date.today().year
        month = _MONTH_MAP.get(month_str)
        if month:
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                pass

    # Pattern 2: Day Month [Year] (e.g. "15 January 2026")
    m = re.match(r"^(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?$", text)
    if m:
        day = int(m.group(1))
        month_str = m.group(2).lower()
        year = int(m.group(3)) if m.group(3) else date.today().year
        month = _MONTH_MAP.get(month_str)
        if month:
            try:
                return date(year, month, day).isoformat()
            except ValueError:
                pass

    # Pattern 3: MM/DD/YYYY or MM-DD-YYYY
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", text)
    if m:
        month_num = int(m.group(1))
        day = int(m.group(2))
        year = int(m.group(3))
        try:
            return date(year, month_num, day).isoformat()
        except ValueError:
            pass

    logger.debug("Could not parse date string: %r", text)
    return None


def _extract_due_date(body_text: str) -> str | None:
    """Search the email body for a due-date line and parse it."""
    if not body_text:
        return None

    match = _RE_DUE_DATE_LINE.search(body_text)
    if match:
        raw_date = match.group(1).strip()
        # Remove trailing punctuation
        raw_date = raw_date.rstrip(".")
        return _parse_relative_date(raw_date)

    return None


def _extract_points(body_text: str) -> int | None:
    """Extract max points from the email body."""
    if not body_text:
        return None

    match = _RE_POINTS_LINE.search(body_text)
    if match:
        try:
            return int(match.group(1))
        except (ValueError, TypeError):
            pass
    return None


def _extract_description(body_text: str) -> str | None:
    """Extract the assignment description from the email body.

    Skips metadata lines (due date, points) and footers, returns the first
    substantive paragraph.
    """
    if not body_text:
        return None

    skip_patterns = [
        re.compile(r"^\s*(?:due|deadline|points?|pts|marks?)\s*:", re.IGNORECASE),
        re.compile(r"^\s*(?:view|open|click|go to|visit)\s", re.IGNORECASE),
        re.compile(r"^\s*(?:google classroom|classroom\.google)", re.IGNORECASE),
        re.compile(r"^\s*https?://", re.IGNORECASE),
        re.compile(r"^\s*$"),
    ]

    paragraphs: list[str] = []
    current_para: list[str] = []

    for line in body_text.splitlines():
        if not line.strip():
            if current_para:
                paragraphs.append("\n".join(current_para))
                current_para = []
            continue
        current_para.append(line)

    if current_para:
        paragraphs.append("\n".join(current_para))

    for para in paragraphs:
        first_line = para.splitlines()[0]
        if any(p.search(first_line) for p in skip_patterns):
            continue
        # Skip very short single-word lines (e.g. "Hi", "Hello")
        if len(para.strip()) < 10 and " " not in para.strip():
            continue
        return para.strip()

    return None


def _extract_assignments_from_body(body_text: str) -> list[dict]:
    """Extract assignments listed in the body of a due-reminder email.

    Some reminder emails list multiple assignments, each on its own line.
    """
    assignments: list[dict] = []
    if not body_text:
        return assignments

    # Look for lines like "• Assignment Title - Due Jan 15" or "- Assignment Title"
    pattern = re.compile(
        r"^\s*[\u2022\-\*]\s+(.+?)(?:\s*[-\u2013\u2014]\s*(?:Due\s+)?(.+))?\s*$",
        re.MULTILINE | re.IGNORECASE,
    )
    for match in pattern.finditer(body_text):
        title = match.group(1).strip()
        due_raw = (match.group(2) or "").strip()
        a: dict = {"title": title}
        if due_raw:
            due_date = _parse_relative_date(due_raw)
            if due_date:
                a["due_date"] = due_date
        assignments.append(a)

    return assignments


def _extract_comment_details(body_text: str) -> tuple[str | None, str | None]:
    """Extract the commenter name and comment text from a comment email body.

    Common patterns:
    - "Teacher Name commented: ..."
    - "Teacher Name wrote: ..."
    - Just the comment text with the name in the first line
    """
    if not body_text:
        return None, None

    # Pattern: "Name commented/wrote: text"
    match = re.match(
        r"^(.+?)\s+(?:commented|wrote|said|replied)\s*:\s*(.+)",
        body_text,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        commenter = match.group(1).strip()
        comment = _strip_email_footer(match.group(2).strip())
        return commenter, comment

    # Pattern: first line is a name, rest is the comment
    lines = body_text.strip().splitlines()
    if len(lines) >= 2:
        first_line = lines[0].strip()
        # Heuristic: if first line is short and looks like a name (no URLs, no punctuation-heavy)
        if (
            len(first_line) < 60
            and not first_line.startswith("http")
            and first_line.count(".") <= 1
            and not re.search(r"[<>\[\]{}]", first_line)
        ):
            comment = _strip_email_footer("\n".join(lines[1:]).strip())
            return first_line, comment

    # Fallback: just return the body as the comment
    return None, _strip_email_footer(body_text)


def _strip_email_footer(text: str) -> str:
    """Remove common email footer/signature content from text."""
    if not text:
        return ""

    # Common footer delimiters
    footer_patterns = [
        re.compile(r"^-{2,}\s*$", re.MULTILINE),
        re.compile(r"^_{2,}\s*$", re.MULTILINE),
        re.compile(r"^Sent from Google Classroom", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^You received this.*because", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^To view this.*click", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^Open in Classroom", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^Google LLC", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^This email was sent to", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^Unsubscribe", re.MULTILINE | re.IGNORECASE),
    ]

    # Find the earliest footer marker and truncate
    earliest_pos = len(text)
    for pattern in footer_patterns:
        match = pattern.search(text)
        if match and match.start() < earliest_pos:
            earliest_pos = match.start()

    return text[:earliest_pos].strip()


def _looks_like_course_name(text: str) -> bool:
    """Heuristic: does this text look like a course name header?

    Course names are typically title-case, short, and do not contain
    status keywords or assignment-like patterns.
    """
    if not text:
        return False
    lower = text.lower()
    # If it contains status keywords, probably not a course name
    if any(kw in lower for kw in ("missing", "turned in", "graded", "due ")):
        return False
    # If it starts with 'Assignment:' / 'Work:', not a course name
    if re.match(r"^(?:assignment|work)\s*:", text, re.IGNORECASE):
        return False
    # Course names are usually shorter and capitalised
    return len(text) < 100 and text[0].isupper()


def _normalise_status(status_raw: str) -> str:
    """Normalise a guardian summary status string."""
    if not status_raw:
        return "unknown"
    lower = status_raw.lower().strip()
    if lower == "missing":
        return "missing"
    if lower == "turned in":
        return "turned_in"
    if lower.startswith("graded"):
        return "graded"
    if lower.startswith("due"):
        return "pending"
    return "unknown"
