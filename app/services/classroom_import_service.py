"""Classroom Data Import service.

Handles the full lifecycle of importing data from Google Classroom into
ClassBridge via copy-paste text or screenshot images:

1. Create an import session
2. Parse text (via Anthropic Claude) or screenshots (via Claude Vision)
3. Preview parsed data with deduplication info
4. Commit reviewed data into the database (courses, assignments, materials)

Part of #57 — Classroom Data Import.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from datetime import datetime

import anthropic
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.assignment import Assignment
from app.models.course import Course
from app.models.course_content import CourseContent
from app.models.import_session import ImportSession

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

# Model used for structured text parsing (fast, cheap, good at JSON)
_PARSE_MODEL = "claude-haiku-4-5-20251001"

# Model used for Vision screenshot extraction
_VISION_MODEL = "claude-haiku-4-5-20251001"

# Empty parsed structure used as a default / fallback
_EMPTY_PARSED: dict = {
    "courses": [],
    "assignments": [],
    "materials": [],
    "announcements": [],
    "grades": [],
}


# ── Anthropic client helper ──────────────────────────────────────────────

def _get_client() -> anthropic.Anthropic:
    """Return a configured Anthropic client using the platform API key."""
    api_key = settings.anthropic_api_key
    if not api_key:
        logger.error("Anthropic API key not configured — cannot run import parsing")
        raise ValueError("ANTHROPIC_API_KEY not configured")
    return anthropic.Anthropic(api_key=api_key)


# ── 1. Session management ───────────────────────────────────────────────

def create_session(
    db: Session,
    user_id: int,
    student_id: int | None,
    source_type: str,
    raw_data: str | None = None,
) -> ImportSession:
    """Create a new ImportSession record with status='processing'.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy session.
    user_id : int
        The user who initiated the import.
    student_id : int | None
        Optional student the import is for.
    source_type : str
        One of "copypaste", "screenshot", "photo".
    raw_data : str | None
        The raw pasted text or metadata about uploaded images.

    Returns
    -------
    ImportSession
        The newly created session (flushed, has an ``id``).
    """
    session = ImportSession(
        user_id=user_id,
        student_id=student_id,
        source_type=source_type,
        status="processing",
        raw_data=raw_data,
    )
    db.add(session)
    db.flush()
    logger.info(
        "Import session created | id=%d user=%d source=%s",
        session.id, user_id, source_type,
    )
    return session


# ── 2. Copy-paste text parsing ──────────────────────────────────────────

_COPYPASTE_SYSTEM_PROMPT = (
    "You are a data-extraction assistant for a K-12 education platform. "
    "You receive raw text that a parent or student has copy-pasted from "
    "Google Classroom. Your job is to extract every identifiable item "
    "and return ONLY valid JSON — no commentary, no markdown fences."
)

_COPYPASTE_USER_TEMPLATE = """\
You are extracting structured data from text copy-pasted from a Google Classroom page.
The user copied text from the "{source_hint}" page. Today's date is {today_date}.

Extract all identifiable items and return ONLY valid JSON:
{{
  "courses": [{{"name": "...", "teacher_name": "...", "section": "..."}}],
  "assignments": [{{"title": "...", "description": "...", "due_date": "YYYY-MM-DD", "max_points": null, "course_name": "...", "status": "..."}}],
  "materials": [{{"title": "...", "description": "...", "type": "...", "url": "..."}}],
  "announcements": [{{"title": "...", "body": "...", "date": "YYYY-MM-DD", "author": "..."}}],
  "grades": [{{"assignment_title": "...", "score": null, "max_score": null, "course_name": "..."}}]
}}

Rules:
- If a field is not present, set to null
- Convert relative dates (e.g. "Due tomorrow") to YYYY-MM-DD using today's date
- Distinguish assignments from announcements from materials
- Extract ALL items, even partial ones
- Return ONLY valid JSON, no commentary

--- TEXT START ---
{text}
--- TEXT END ---"""


async def parse_copypaste(
    text: str,
    source_hint: str = "auto",
    today_date: str | None = None,
) -> dict:
    """Send pasted text to Claude for structured extraction.

    Parameters
    ----------
    text : str
        Raw text copied from Google Classroom.
    source_hint : str
        One of "assignment_list", "assignment_detail", "stream",
        "people", "auto".  Helps the model understand the layout.
    today_date : str | None
        ISO date string (YYYY-MM-DD).  Defaults to today if not provided.

    Returns
    -------
    dict
        Parsed JSON matching the canonical import structure.
    """
    if not text or not text.strip():
        logger.warning("parse_copypaste called with empty text")
        return dict(_EMPTY_PARSED)

    if today_date is None:
        today_date = datetime.now().strftime("%Y-%m-%d")

    prompt = _COPYPASTE_USER_TEMPLATE.format(
        source_hint=source_hint,
        today_date=today_date,
        text=text[:15000],  # Limit to ~15k chars to stay within context
    )

    start = time.time()
    try:
        client = _get_client()
        response = client.messages.create(
            model=_PARSE_MODEL,
            max_tokens=4096,
            system=_COPYPASTE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        raw_response = response.content[0].text.strip()
        duration_ms = (time.time() - start) * 1000
        logger.info(
            "parse_copypaste completed | duration=%.1fms tokens_in=%d tokens_out=%d",
            duration_ms, response.usage.input_tokens, response.usage.output_tokens,
        )
        return _safe_parse_json(raw_response)
    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        logger.error("parse_copypaste failed | duration=%.1fms error=%s", duration_ms, e)
        raise


# ── 3. Screenshot / image parsing (Vision) ──────────────────────────────

_VISION_SYSTEM_PROMPT = (
    "You are a data-extraction assistant for a K-12 education platform. "
    "You receive screenshot images of Google Classroom pages. "
    "Your job is to visually inspect the UI and extract every identifiable "
    "item, returning ONLY valid JSON — no commentary, no markdown fences."
)

_VISION_USER_TEMPLATE = """\
You are extracting structured data from screenshot(s) of a Google Classroom page.
The screenshot appears to be from the "{source_hint}" view. Today's date is {today_date}.

Carefully inspect the Google Classroom UI in the image(s) and identify:
- Course headers (course name, teacher name, section)
- Assignment cards (title, description, due date, points, status)
- Announcements (title, body, date, author)
- Materials (title, description, type, link)
- Grade information (assignment title, score, max score, course)

Return ONLY valid JSON with this structure:
{{
  "courses": [{{"name": "...", "teacher_name": "...", "section": "..."}}],
  "assignments": [{{"title": "...", "description": "...", "due_date": "YYYY-MM-DD", "max_points": null, "course_name": "...", "status": "..."}}],
  "materials": [{{"title": "...", "description": "...", "type": "...", "url": "..."}}],
  "announcements": [{{"title": "...", "body": "...", "date": "YYYY-MM-DD", "author": "..."}}],
  "grades": [{{"assignment_title": "...", "score": null, "max_score": null, "course_name": "..."}}]
}}

Rules:
- If a field is not visible or readable, set to null
- Convert relative dates (e.g. "Due tomorrow") to YYYY-MM-DD using today's date
- Distinguish assignments from announcements from materials based on Google Classroom UI cues
- Extract ALL visible items, even partially visible ones
- Return ONLY valid JSON, no commentary"""


def _detect_image_media_type(img_bytes: bytes) -> str:
    """Detect image MIME type from magic bytes."""
    if img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png"
    if img_bytes[:2] == b'\xff\xd8':
        return "image/jpeg"
    if img_bytes[:4] == b'GIF8':
        return "image/gif"
    if img_bytes[:4] == b'RIFF':
        return "image/webp"
    # Default fallback
    return "image/png"


async def parse_screenshots(
    image_bytes_list: list[bytes],
    source_hint: str = "auto",
    today_date: str | None = None,
) -> dict:
    """Send screenshot images to Claude Vision for structured extraction.

    All images are batched into a single API call to minimise latency and
    cost.

    Parameters
    ----------
    image_bytes_list : list[bytes]
        List of raw image byte buffers (PNG, JPEG, etc.).
    source_hint : str
        Hint about which Google Classroom page was captured.
    today_date : str | None
        ISO date string (YYYY-MM-DD).  Defaults to today if not provided.

    Returns
    -------
    dict
        Parsed JSON matching the canonical import structure.
    """
    if not image_bytes_list:
        logger.warning("parse_screenshots called with no images")
        return dict(_EMPTY_PARSED)

    if today_date is None:
        today_date = datetime.now().strftime("%Y-%m-%d")

    # Build multi-modal content blocks
    content_blocks: list[dict] = []

    # Text instruction first
    content_blocks.append({
        "type": "text",
        "text": _VISION_USER_TEMPLATE.format(
            source_hint=source_hint,
            today_date=today_date,
        ),
    })

    # Append each image
    for img_bytes in image_bytes_list:
        if len(img_bytes) < 512:
            # Skip trivially small images (likely broken / placeholder)
            continue
        media_type = _detect_image_media_type(img_bytes)
        b64_data = base64.b64encode(img_bytes).decode("utf-8")
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64_data,
            },
        })

    # If no valid images remained after filtering, return empty
    if len(content_blocks) <= 1:
        logger.warning("parse_screenshots: all images were too small / invalid")
        return dict(_EMPTY_PARSED)

    start = time.time()
    try:
        client = _get_client()
        response = client.messages.create(
            model=_VISION_MODEL,
            max_tokens=4096,
            system=_VISION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content_blocks}],
            temperature=0.0,
        )
        raw_response = response.content[0].text.strip()
        duration_ms = (time.time() - start) * 1000
        logger.info(
            "parse_screenshots completed | duration=%.1fms images=%d tokens_in=%d tokens_out=%d",
            duration_ms,
            len(image_bytes_list),
            response.usage.input_tokens,
            response.usage.output_tokens,
        )
        return _safe_parse_json(raw_response)
    except Exception as e:
        duration_ms = (time.time() - start) * 1000
        logger.error("parse_screenshots failed | duration=%.1fms error=%s", duration_ms, e)
        raise


# ── 4. Preview session ──────────────────────────────────────────────────

def preview_session(db: Session, session_id: int) -> dict:
    """Return parsed data for frontend preview, enriched with dedup flags.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy session.
    session_id : int
        The ImportSession to preview.

    Returns
    -------
    dict
        The parsed data with ``_is_duplicate`` flags on each item.

    Raises
    ------
    ValueError
        If the session does not exist or has no parsed data.
    """
    imp = db.query(ImportSession).filter(ImportSession.id == session_id).first()
    if not imp:
        raise ValueError(f"Import session {session_id} not found")
    if not imp.parsed_data:
        raise ValueError(f"Import session {session_id} has no parsed data yet")

    parsed = json.loads(imp.parsed_data)
    enriched = _check_duplicates(db, parsed, imp.user_id)

    return {
        "session_id": imp.id,
        "status": imp.status,
        "source_type": imp.source_type,
        "created_at": imp.created_at.isoformat() if imp.created_at else None,
        "data": enriched,
    }


# ── 5. Commit session ──────────────────────────────────────────────────

def commit_session(db: Session, session_id: int, user_id: int) -> dict:
    """Commit reviewed (or parsed) data into the database.

    For each item the service uses find-or-create semantics keyed on
    a SHA-256 dedup hash stored in ``lms_external_id``.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy session.
    session_id : int
        The ImportSession to commit.
    user_id : int
        The user performing the import (for ownership / audit).

    Returns
    -------
    dict
        Summary counters: session_id, courses_created, assignments_created,
        materials_created, duplicates_skipped.

    Raises
    ------
    ValueError
        If the session does not exist or is already imported.
    """
    imp = db.query(ImportSession).filter(ImportSession.id == session_id).first()
    if not imp:
        raise ValueError(f"Import session {session_id} not found")
    if imp.status == "imported":
        raise ValueError(f"Import session {session_id} is already imported")

    # Prefer user-reviewed data; fall back to raw AI parse
    data_json = imp.reviewed_data or imp.parsed_data
    if not data_json:
        raise ValueError(f"Import session {session_id} has no data to commit")

    data = json.loads(data_json)

    courses_created = 0
    assignments_created = 0
    materials_created = 0
    duplicates_skipped = 0

    # ── Map course name → Course ORM for assignment/material linking ──
    course_map: dict[str, Course] = {}

    # Create / find courses
    for course_data in data.get("courses", []):
        course_name = (course_data.get("name") or "").strip()
        if not course_name:
            continue

        dedup_hash = _generate_dedup_hash(course_name, "", "")
        existing = (
            db.query(Course)
            .filter(
                Course.lms_external_id == dedup_hash,
                Course.lms_provider == "manual_import",
            )
            .first()
        )
        if existing:
            course_map[course_name.lower()] = existing
            duplicates_skipped += 1
            continue

        course = Course(
            name=course_name,
            description=course_data.get("section"),
            classroom_type="school",
            lms_provider="manual_import",
            lms_external_id=dedup_hash,
            created_by_user_id=user_id,
        )
        db.add(course)
        db.flush()
        course_map[course_name.lower()] = course
        courses_created += 1

    # ── Helper: resolve a course by name ──
    def _resolve_course(course_name: str | None) -> Course | None:
        if not course_name:
            return None
        key = course_name.strip().lower()
        if key in course_map:
            return course_map[key]
        # Try a DB lookup by name for courses the user already has
        existing = (
            db.query(Course)
            .filter(Course.name.ilike(f"%{key}%"))
            .filter(Course.created_by_user_id == user_id)
            .first()
        )
        if existing:
            course_map[key] = existing
            return existing
        # Auto-create a minimal course so the assignment has somewhere to live
        auto_hash = _generate_dedup_hash(course_name.strip(), "", "")
        course = Course(
            name=course_name.strip(),
            classroom_type="school",
            lms_provider="manual_import",
            lms_external_id=auto_hash,
            created_by_user_id=user_id,
        )
        db.add(course)
        db.flush()
        course_map[key] = course
        courses_created += 0  # Don't count auto-created (already counted above)
        return course

    # Create / find assignments
    for asn_data in data.get("assignments", []):
        title = (asn_data.get("title") or "").strip()
        if not title:
            continue

        course_name = asn_data.get("course_name") or ""
        due_date_str = asn_data.get("due_date") or ""
        dedup_hash = _generate_dedup_hash(title, course_name, due_date_str)

        existing = (
            db.query(Assignment)
            .filter(
                Assignment.lms_external_id == dedup_hash,
                Assignment.lms_provider == "manual_import",
            )
            .first()
        )
        if existing:
            duplicates_skipped += 1
            continue

        course = _resolve_course(course_name)

        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d")
            except ValueError:
                pass

        max_points = asn_data.get("max_points")
        if max_points is not None:
            try:
                max_points = float(max_points)
            except (ValueError, TypeError):
                max_points = None

        assignment = Assignment(
            title=title,
            description=asn_data.get("description"),
            course_id=course.id if course else None,
            lms_provider="manual_import",
            lms_external_id=dedup_hash,
            due_date=due_date,
            max_points=max_points,
        )
        db.add(assignment)
        db.flush()
        assignments_created += 1

    # Create / find materials
    for mat_data in data.get("materials", []):
        title = (mat_data.get("title") or "").strip()
        if not title:
            continue

        course_name = mat_data.get("course_name") or ""
        dedup_hash = _generate_dedup_hash(title, course_name, "")

        existing = (
            db.query(CourseContent)
            .filter(
                CourseContent.lms_external_id == dedup_hash,
                CourseContent.lms_provider == "manual_import",
            )
            .first()
        )
        if existing:
            duplicates_skipped += 1
            continue

        course = _resolve_course(course_name)

        content = CourseContent(
            course_id=course.id if course else None,
            title=title,
            description=mat_data.get("description") or "",
            content_type="resources",
            reference_url=mat_data.get("url"),
            lms_provider="manual_import",
            lms_external_id=dedup_hash,
            created_by_user_id=user_id,
        )
        db.add(content)
        db.flush()
        materials_created += 1

    # ── Update session record ────────────────────────────────────────
    imp.status = "imported"
    imp.courses_created = courses_created
    imp.assignments_created = assignments_created
    imp.materials_created = materials_created
    imp.duplicates_skipped = duplicates_skipped
    imp.imported_at = datetime.utcnow()

    db.commit()

    logger.info(
        "Import session committed | id=%d courses=%d assignments=%d materials=%d dupes=%d",
        session_id, courses_created, assignments_created, materials_created, duplicates_skipped,
    )

    return {
        "session_id": session_id,
        "courses_created": courses_created,
        "assignments_created": assignments_created,
        "materials_created": materials_created,
        "duplicates_skipped": duplicates_skipped,
    }


# ── 6. Dedup hash generation ───────────────────────────────────────────

def _generate_dedup_hash(title: str, course_name: str, due_date: str) -> str:
    """Generate a SHA-256 dedup hash from normalised title + course + date.

    Used as ``lms_external_id`` for manual-import records so that
    re-importing the same data doesn't create duplicates.

    Parameters
    ----------
    title : str
        Item title (assignment name, material name, etc.).
    course_name : str
        The course the item belongs to.
    due_date : str
        Due date in YYYY-MM-DD format (or empty string).

    Returns
    -------
    str
        64-character hex digest prefixed with ``imp_`` for easy identification.
    """
    normalised = "|".join(
        s.strip().lower() for s in [title, course_name, due_date]
    )
    digest = hashlib.sha256(normalised.encode("utf-8")).hexdigest()
    return f"imp_{digest}"


# ── 7. Duplicate checking ──────────────────────────────────────────────

def _check_duplicates(db: Session, parsed_data: dict, user_id: int) -> dict:
    """Annotate each item in parsed_data with an ``_is_duplicate`` flag.

    Checks whether a record with a matching dedup hash already exists in
    the database.

    Parameters
    ----------
    db : Session
        Active SQLAlchemy session.
    parsed_data : dict
        The canonical parsed structure.
    user_id : int
        Used to scope course lookups.

    Returns
    -------
    dict
        A copy of parsed_data with ``_is_duplicate: bool`` on each item.
    """
    result = {}

    # ── Courses ──
    courses = []
    for c in parsed_data.get("courses", []):
        name = (c.get("name") or "").strip()
        dedup_hash = _generate_dedup_hash(name, "", "")
        exists = (
            db.query(Course.id)
            .filter(
                Course.lms_external_id == dedup_hash,
                Course.lms_provider == "manual_import",
            )
            .first()
        ) is not None
        courses.append({**c, "_is_duplicate": exists})
    result["courses"] = courses

    # ── Assignments ──
    assignments = []
    for a in parsed_data.get("assignments", []):
        title = (a.get("title") or "").strip()
        course_name = a.get("course_name") or ""
        due_date = a.get("due_date") or ""
        dedup_hash = _generate_dedup_hash(title, course_name, due_date)
        exists = (
            db.query(Assignment.id)
            .filter(
                Assignment.lms_external_id == dedup_hash,
                Assignment.lms_provider == "manual_import",
            )
            .first()
        ) is not None
        assignments.append({**a, "_is_duplicate": exists})
    result["assignments"] = assignments

    # ── Materials ──
    materials = []
    for m in parsed_data.get("materials", []):
        title = (m.get("title") or "").strip()
        course_name = m.get("course_name") or ""
        dedup_hash = _generate_dedup_hash(title, course_name, "")
        exists = (
            db.query(CourseContent.id)
            .filter(
                CourseContent.lms_external_id == dedup_hash,
                CourseContent.lms_provider == "manual_import",
            )
            .first()
        ) is not None
        materials.append({**m, "_is_duplicate": exists})
    result["materials"] = materials

    # ── Announcements & grades (no DB model yet — pass through) ──
    announcements = []
    for ann in parsed_data.get("announcements", []):
        announcements.append({**ann, "_is_duplicate": False})
    result["announcements"] = announcements

    grades = []
    for g in parsed_data.get("grades", []):
        grades.append({**g, "_is_duplicate": False})
    result["grades"] = grades

    return result


# ── Utility: safe JSON parsing ──────────────────────────────────────────

def _safe_parse_json(raw: str) -> dict:
    """Attempt to parse JSON from an LLM response, stripping markdown fences.

    The model *should* return bare JSON, but sometimes wraps it in
    ```json ... ``` fences.  This helper handles both cases gracefully.

    Returns the empty structure on parse failure rather than raising.
    """
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = text.index("\n") if "\n" in text else len(text)
        text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3].rstrip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            # Ensure all expected keys are present
            for key in _EMPTY_PARSED:
                if key not in parsed:
                    parsed[key] = []
            return parsed
        logger.warning("AI returned non-dict JSON: %s", type(parsed).__name__)
        return dict(_EMPTY_PARSED)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse AI response as JSON: %s | raw=%s", e, text[:500])
        return dict(_EMPTY_PARSED)
