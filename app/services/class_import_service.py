"""Service helpers for CB-ONBOARD-001 bulk class import (#3985).

Reuses the existing teacher-resolution + invite flow from courses.py so
that a row imported from Google Classroom or a parsed screenshot goes
through exactly the same shadow-teacher / invite-email path as a single
course created via POST /api/courses/.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.api.routes.courses import (
    _resolve_teacher_by_email,
    generate_class_code,
)
from app.models.course import Course
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.schemas.class_import import BulkCreateRow
from app.services.ai_service import get_anthropic_client  # re-exported for patching in tests

logger = logging.getLogger(__name__)


def _compose_description(section: str | None) -> str | None:
    """Store the screenshot/GC 'section' line inside the Course.description."""
    if not section:
        return None
    return f"Section: {section.strip()}"


def _find_existing_by_gc_id(db: Session, gc_id: str | None) -> Course | None:
    if not gc_id:
        return None
    return db.query(Course).filter(Course.google_classroom_id == gc_id).first()


def _ensure_or_invite_teacher(
    db: Session,
    row: BulkCreateRow,
    current_user: User,
    course: Course,
) -> None:
    """Resolve (or invite) the teacher for a single import row.

    Mirrors create_course: prefer teacher_email -> user-based match, else
    shadow-teacher + invite. When no email, create a shadow teacher with just
    the name.
    """
    if row.teacher_email:
        teacher_id = _resolve_teacher_by_email(
            db, row.teacher_email, current_user, course
        )
        if teacher_id:
            course.teacher_id = teacher_id
            course.is_private = False
        else:
            # No platform user — fall back to shadow teacher so the course
            # still has a visible name.
            shadow = (
                db.query(Teacher)
                .filter(Teacher.google_email == row.teacher_email.strip().lower())
                .first()
            )
            if not shadow:
                shadow = Teacher(
                    is_shadow=True,
                    is_platform_user=False,
                    full_name=row.teacher_name.strip(),
                    google_email=row.teacher_email.strip().lower(),
                )
                db.add(shadow)
                db.flush()
            course.teacher_id = shadow.id
            course.is_private = False
        return

    # No email at all — shadow teacher keyed on name only (not unique).
    shadow = Teacher(
        is_shadow=True,
        is_platform_user=False,
        full_name=row.teacher_name.strip(),
    )
    db.add(shadow)
    db.flush()
    course.teacher_id = shadow.id
    course.is_private = False


def import_one_row(
    db: Session,
    row: BulkCreateRow,
    current_user: User,
) -> Course:
    """Create a single Course from one bulk-import row.

    Raises ``AlreadyImportedError`` with existing_course_id when the row
    already exists (by google_classroom_id). Any other error is raised for
    the caller to capture into the failed list.
    """
    existing = _find_existing_by_gc_id(db, row.google_classroom_id)
    if existing:
        raise AlreadyImportedError(existing.id)

    # Role-driven defaults (match create_course behavior).
    is_private = True
    if current_user.has_role(UserRole.TEACHER):
        is_private = False

    course = Course(
        name=row.class_name.strip(),
        description=_compose_description(row.section),
        created_by_user_id=current_user.id,
        is_private=is_private,
        google_classroom_id=(
            row.google_classroom_id.strip() if row.google_classroom_id else None
        ),
        class_code=generate_class_code(db),
    )
    db.add(course)
    db.flush()

    _ensure_or_invite_teacher(db, row, current_user, course)

    return course


class AlreadyImportedError(Exception):
    """Signals a row that should be skipped because the course already exists."""

    def __init__(self, existing_course_id: int):
        self.existing_course_id = existing_course_id
        super().__init__(f"Course already imported (id={existing_course_id})")


# ── Screenshot parsing ────────────────────────────────────────────────

VISION_PROMPT = """You are reading a screenshot of a Google Classroom home page.

Extract the list of class cards visible in the image. For each class card, return:
  - class_name: the main class title EXACTLY as shown (preserve truncation "..." or "…" if present)
  - section: the small subtitle/section line under the title (e.g. "8 FI", "Intermediate", "2025-2024"). Use null if not present.
  - teacher_name: the teacher name shown on the card, exactly as shown (do not change case).

Return ONLY a JSON array. Do NOT wrap in markdown code fences. Do NOT include any prose, commentary, or explanation. If no class cards are visible, return [].

Do NOT include assignments, announcements, dates, notifications, or anything that is not a class card.

Example output:
[{"class_name": "GRADE 8 FI Schmidt", "section": "8 FI", "teacher_name": "melanie schmidt"}]
"""


def strip_code_fences(text: str) -> str:
    """Safely strip markdown code fences the model may emit despite instructions."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # Remove the opening fence (possibly ```json)
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        # Remove the closing fence
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
    return stripped.strip()


def parse_screenshot_with_vision(
    image_bytes: bytes,
    media_type: str,
    model: str | None = None,
) -> list[dict]:
    """Call Claude vision with the screenshot and return parsed rows.

    Raises ValueError on parse failure (caller converts to 422).
    """
    import base64
    import json

    from app.core.config import settings

    client = get_anthropic_client()
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")

    message = client.messages.create(
        model=model or settings.claude_model or "claude-sonnet-4-6",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }
        ],
    )

    # Extract the text block. Anthropic SDK returns a list of content blocks.
    text_out = ""
    for block in message.content:
        if getattr(block, "type", None) == "text":
            text_out = block.text
            break
    if not text_out:
        raise ValueError("Empty response from vision model")

    cleaned = strip_code_fences(text_out)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning("Vision returned malformed JSON: %s | raw=%r", e, text_out[:200])
        raise ValueError("malformed JSON from vision model") from e

    if not isinstance(parsed, list):
        raise ValueError("vision output must be a JSON array")

    # Normalize — keep only allowed keys; enforce string types.
    normalized: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        cn = item.get("class_name")
        tn = item.get("teacher_name")
        if not cn or not tn:
            continue
        normalized.append(
            {
                "class_name": str(cn).strip(),
                "section": (str(item["section"]).strip() if item.get("section") else None),
                "teacher_name": str(tn).strip(),
                "teacher_email": None,
            }
        )
    return normalized
