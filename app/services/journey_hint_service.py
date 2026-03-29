"""
Journey Hint Detection Service
Determines which contextual hint to show based on real user state.
Smart rules: state-based, frequency-capped, behavior-aware.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.models.journey_hint import JourneyHint
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hint definitions
# ---------------------------------------------------------------------------

HINT_DEFINITIONS: list[dict] = [
    {
        "hint_key": "welcome_modal",
        "roles": {UserRole.PARENT, UserRole.STUDENT, UserRole.TEACHER, UserRole.ADMIN},
        "pages": None,  # any page
        "title": "Welcome to ClassBridge!",
        "description": "Let us help you get started with a quick overview.",
        "journey_id": "W01",
    },
    {
        "hint_key": "parent.add_child",
        "roles": {UserRole.PARENT},
        "pages": {"dashboard", "my-kids"},
        "title": "Add your first child to get started",
        "description": "Link your child to see their courses and progress.",
        "journey_id": "P02",
    },
    {
        "hint_key": "parent.upload_material",
        "roles": {UserRole.PARENT},
        "pages": {"courses"},
        "title": "Upload course materials",
        "description": "Add notes, assignments, or readings to help your child study.",
        "journey_id": "P03",
    },
    {
        "hint_key": "parent.connect_google",
        "roles": {UserRole.PARENT},
        "pages": {"courses", "settings"},
        "title": "Connect Google Classroom",
        "description": "Sync your child's courses and assignments automatically.",
        "journey_id": "P04",
    },
    {
        "hint_key": "parent.send_message",
        "roles": {UserRole.PARENT},
        "pages": {"my-kids", "messages"},
        "title": "Send your first message",
        "description": "Communicate with your child's teachers directly.",
        "journey_id": "P05",
    },
    {
        "hint_key": "student.first_guide",
        "roles": {UserRole.STUDENT},
        "pages": {"study-hub", "course-detail"},
        "title": "Create your first study guide",
        "description": "Generate an AI-powered study guide from your course materials.",
        "journey_id": "S02",
    },
    {
        "hint_key": "student.first_quiz",
        "roles": {UserRole.STUDENT},
        "pages": {"study-guide-detail"},
        "title": "Take your first quiz",
        "description": "Test your knowledge with an AI-generated quiz.",
        "journey_id": "S03",
    },
    {
        "hint_key": "student.flashcards",
        "roles": {UserRole.STUDENT},
        "pages": {"study-guide-detail"},
        "title": "Try flashcards",
        "description": "Review key concepts with AI-generated flashcards.",
        "journey_id": "S04",
    },
    {
        "hint_key": "teacher.create_course",
        "roles": {UserRole.TEACHER},
        "pages": {"dashboard", "courses"},
        "title": "Create your first course",
        "description": "Set up a course so students can join and access materials.",
        "journey_id": "T02",
    },
    {
        "hint_key": "teacher.add_students",
        "roles": {UserRole.TEACHER},
        "pages": {"course-detail"},
        "title": "Add students to your course",
        "description": "Invite students so they can access course materials.",
        "journey_id": "T03",
    },
]

_HINT_MAP: dict[str, dict] = {h["hint_key"]: h for h in HINT_DEFINITIONS}


# ---------------------------------------------------------------------------
# State-detection helpers (one per hint_key)
# ---------------------------------------------------------------------------

def _check_welcome_modal(db: Session, user: User) -> bool:
    """True when user has NO journey_hints rows at all (brand-new)."""
    count = db.query(sa_func.count(JourneyHint.id)).filter(
        JourneyHint.user_id == user.id,
    ).scalar()
    return count == 0


def _check_parent_add_child(db: Session, user: User) -> bool:
    from app.models.student import parent_students
    count = db.query(sa_func.count()).select_from(parent_students).filter(
        parent_students.c.parent_id == user.id,
    ).scalar()
    return count == 0


def _check_parent_upload_material(db: Session, user: User) -> bool:
    from app.models.student import parent_students
    from app.models.course_content import CourseContent
    # Must have children first
    child_count = db.query(sa_func.count()).select_from(parent_students).filter(
        parent_students.c.parent_id == user.id,
    ).scalar()
    if child_count == 0:
        return False
    content_count = db.query(sa_func.count(CourseContent.id)).filter(
        CourseContent.created_by_user_id == user.id,
    ).scalar()
    return content_count == 0


def _check_parent_connect_google(db: Session, user: User) -> bool:
    return not user.google_access_token


def _check_parent_send_message(db: Session, user: User) -> bool:
    from app.models.message import Message
    count = db.query(sa_func.count(Message.id)).filter(
        Message.sender_id == user.id,
    ).scalar()
    return count == 0


def _check_student_first_guide(db: Session, user: User) -> bool:
    from app.models.study_guide import StudyGuide
    count = db.query(sa_func.count(StudyGuide.id)).filter(
        StudyGuide.user_id == user.id,
    ).scalar()
    return count == 0


def _check_student_first_quiz(db: Session, user: User) -> bool:
    from app.models.study_guide import StudyGuide
    from app.models.quiz_result import QuizResult
    guide_count = db.query(sa_func.count(StudyGuide.id)).filter(
        StudyGuide.user_id == user.id,
    ).scalar()
    if guide_count == 0:
        return False
    quiz_count = db.query(sa_func.count(QuizResult.id)).filter(
        QuizResult.user_id == user.id,
    ).scalar()
    return quiz_count == 0


def _check_student_flashcards(db: Session, user: User) -> bool:
    from app.models.study_guide import StudyGuide
    count = db.query(sa_func.count(StudyGuide.id)).filter(
        StudyGuide.user_id == user.id,
        StudyGuide.guide_type == "flashcards",
    ).scalar()
    return count == 0


def _check_teacher_create_course(db: Session, user: User) -> bool:
    from app.models.course import Course
    count = db.query(sa_func.count(Course.id)).filter(
        Course.created_by_user_id == user.id,
    ).scalar()
    return count == 0


def _check_teacher_add_students(db: Session, user: User) -> bool:
    from app.models.course import Course, student_courses
    courses = db.query(Course.id).filter(
        Course.created_by_user_id == user.id,
    ).all()
    if not courses:
        return False
    course_ids = [c.id for c in courses]
    enrollment_count = db.query(sa_func.count()).select_from(student_courses).filter(
        student_courses.c.course_id.in_(course_ids),
    ).scalar()
    return enrollment_count == 0


_STATE_CHECKS: dict[str, callable] = {
    "welcome_modal": _check_welcome_modal,
    "parent.add_child": _check_parent_add_child,
    "parent.upload_material": _check_parent_upload_material,
    "parent.connect_google": _check_parent_connect_google,
    "parent.send_message": _check_parent_send_message,
    "student.first_guide": _check_student_first_guide,
    "student.first_quiz": _check_student_first_quiz,
    "student.flashcards": _check_student_flashcards,
    "teacher.create_course": _check_teacher_create_course,
    "teacher.add_students": _check_teacher_add_students,
}


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------

def get_hint_for_user(
    db: Session,
    user: User,
    page: str,
) -> Optional[dict]:
    """Return the highest-priority applicable hint, or None.

    Applies frequency caps, suppression, snooze, and state-based detection.
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # ── Global suppression ──────────────────────────────────────────
    suppress = db.query(JourneyHint).filter(
        JourneyHint.user_id == user.id,
        JourneyHint.status == "suppress_all",
    ).first()
    if suppress:
        return None

    # ── Account age > 30 days → no hints ────────────────────────────
    if user.created_at:
        created = user.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if (now - created) > timedelta(days=30):
            return None

    # ── Consecutive dismissals check (2+ in last 14 days) ──────────
    recent_dismissed = db.query(sa_func.count(JourneyHint.id)).filter(
        JourneyHint.user_id == user.id,
        JourneyHint.status == "dismissed",
        JourneyHint.dismissed_at >= now - timedelta(days=14),
    ).scalar()
    if recent_dismissed >= 2:
        return None

    # ── Already shown a hint today ──────────────────────────────────
    shown_today = db.query(sa_func.count(JourneyHint.id)).filter(
        JourneyHint.user_id == user.id,
        JourneyHint.status == "shown",
        JourneyHint.shown_at >= today_start,
    ).scalar()
    if shown_today > 0:
        return None

    # ── Evaluate each hint in priority order ────────────────────────
    user_roles = set(user.get_roles_list()) if user.roles else ({user.role} if user.role else set())

    for hint_def in HINT_DEFINITIONS:
        hint_key = hint_def["hint_key"]

        # Role match
        if not (user_roles & hint_def["roles"]):
            continue

        # Page match (None = any page)
        if hint_def["pages"] is not None and page not in hint_def["pages"]:
            continue

        # Check journey_hints: skip if dismissed or completed
        existing = db.query(JourneyHint).filter(
            JourneyHint.user_id == user.id,
            JourneyHint.hint_key == hint_key,
        ).first()

        if existing:
            if existing.status in ("dismissed", "completed"):
                continue
            # Check snooze
            if existing.snooze_until:
                snooze_until = existing.snooze_until
                if snooze_until.tzinfo is None:
                    snooze_until = snooze_until.replace(tzinfo=timezone.utc)
                if snooze_until > now:
                    continue

        # Run state detection
        check_fn = _STATE_CHECKS.get(hint_key)
        if check_fn and not check_fn(db, user):
            continue

        # Hint applies — build response
        journey_id = hint_def["journey_id"]
        return {
            "hint_key": hint_key,
            "title": hint_def["title"],
            "description": hint_def["description"],
            "journey_id": journey_id,
            "journey_url": f"/help#journey-{journey_id.lower()}",
            "diagram_url": f"/help/journeys/{journey_id.lower()}.svg",
        }

    return None


# ---------------------------------------------------------------------------
# Mutation helpers
# ---------------------------------------------------------------------------

def record_hint_shown(db: Session, user_id: int, hint_key: str) -> None:
    """Record that a hint was shown to the user."""
    entry = JourneyHint(
        user_id=user_id,
        hint_key=hint_key,
        status="shown",
    )
    db.add(entry)
    db.commit()


def dismiss_hint(db: Session, user_id: int, hint_key: str) -> None:
    """Mark a hint as dismissed so it won't appear again."""
    existing = db.query(JourneyHint).filter(
        JourneyHint.user_id == user_id,
        JourneyHint.hint_key == hint_key,
    ).first()
    now = datetime.now(timezone.utc)
    if existing:
        existing.status = "dismissed"
        existing.dismissed_at = now
    else:
        entry = JourneyHint(
            user_id=user_id,
            hint_key=hint_key,
            status="dismissed",
            dismissed_at=now,
        )
        db.add(entry)
    db.commit()


def snooze_hint(db: Session, user_id: int, hint_key: str, days: int = 7) -> None:
    """Snooze a hint for the given number of days."""
    now = datetime.now(timezone.utc)
    snooze_until = now + timedelta(days=days)
    existing = db.query(JourneyHint).filter(
        JourneyHint.user_id == user_id,
        JourneyHint.hint_key == hint_key,
    ).first()
    if existing:
        existing.snooze_until = snooze_until
    else:
        entry = JourneyHint(
            user_id=user_id,
            hint_key=hint_key,
            status="shown",
            snooze_until=snooze_until,
        )
        db.add(entry)
    db.commit()


def suppress_all_hints(db: Session, user_id: int) -> None:
    """Suppress all hints for the user permanently."""
    existing = db.query(JourneyHint).filter(
        JourneyHint.user_id == user_id,
        JourneyHint.status == "suppress_all",
    ).first()
    if not existing:
        entry = JourneyHint(
            user_id=user_id,
            hint_key="__suppress_all__",
            status="suppress_all",
        )
        db.add(entry)
        db.commit()


# ---------------------------------------------------------------------------
# Aliases (used by API routes in #2606)
# ---------------------------------------------------------------------------

get_applicable_hint = get_hint_for_user
record_shown = record_hint_shown
