"""Journey Hint detection service — stub for parallel development.

The authoritative version is created by Stream 5 (#2605).
This stub provides the minimum needed to run the API endpoints.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.journey_hint import JourneyHint
from app.models.user import User


# ── Hint definitions (stub — full version in #2605) ──

_HINT_DEFS: dict[str, dict] = {
    "link_your_child": {
        "title": "Link Your Child",
        "description": "Connect your child's account to see their courses and grades.",
        "journey_id": "parent-onboarding",
        "journey_url": "/dashboard/my-kids",
        "diagram_url": "/assets/journeys/parent-onboarding.svg",
        "pages": ["dashboard"],
        "roles": ["PARENT"],
    },
    "join_a_course": {
        "title": "Join a Course",
        "description": "Enroll in your first course to start learning.",
        "journey_id": "student-onboarding",
        "journey_url": "/dashboard/courses",
        "diagram_url": "/assets/journeys/student-onboarding.svg",
        "pages": ["dashboard", "courses"],
        "roles": ["STUDENT"],
    },
}


def get_applicable_hint(
    db: Session, user: User, page: Optional[str] = None
) -> Optional[dict]:
    """Return at most one applicable hint for the user on the given page."""
    now = datetime.now(timezone.utc)

    # Check if user has suppressed all hints
    suppressed = (
        db.query(JourneyHint)
        .filter(
            JourneyHint.user_id == user.id,
            JourneyHint.status == "suppressed",
        )
        .first()
    )
    if suppressed:
        return None

    user_role = user.role.name if hasattr(user.role, "name") else str(user.role)

    for hint_key, defn in _HINT_DEFS.items():
        # Role check
        if user_role not in defn["roles"]:
            continue

        # Page check
        if page and page not in defn["pages"]:
            continue

        # Check if already dismissed
        existing = (
            db.query(JourneyHint)
            .filter(
                JourneyHint.user_id == user.id,
                JourneyHint.hint_key == hint_key,
            )
            .first()
        )
        if existing:
            if existing.status == "dismissed":
                continue
            if existing.status == "snoozed" and existing.snoozed_until:
                # Compare as naive UTC to avoid naive/aware mismatch (SQLite stores naive)
                snoozed = existing.snoozed_until.replace(tzinfo=None)
                if snoozed > now.replace(tzinfo=None):
                    continue

        return {
            "hint_key": hint_key,
            "title": defn["title"],
            "description": defn["description"],
            "journey_id": defn["journey_id"],
            "journey_url": defn["journey_url"],
            "diagram_url": defn["diagram_url"],
        }

    return None


def record_shown(db: Session, user_id: int, hint_key: str) -> None:
    """Record that a hint was shown to the user."""
    existing = (
        db.query(JourneyHint)
        .filter(JourneyHint.user_id == user_id, JourneyHint.hint_key == hint_key)
        .first()
    )
    if not existing:
        db.add(JourneyHint(user_id=user_id, hint_key=hint_key, status="shown"))
        db.commit()


def dismiss_hint(db: Session, user_id: int, hint_key: str) -> None:
    """Permanently dismiss a hint for a user."""
    existing = (
        db.query(JourneyHint)
        .filter(JourneyHint.user_id == user_id, JourneyHint.hint_key == hint_key)
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.status = "dismissed"
        existing.dismissed_at = now
    else:
        db.add(JourneyHint(user_id=user_id, hint_key=hint_key, status="dismissed", dismissed_at=now))
    db.commit()


def snooze_hint(db: Session, user_id: int, hint_key: str) -> None:
    """Snooze a hint for 7 days."""
    existing = (
        db.query(JourneyHint)
        .filter(JourneyHint.user_id == user_id, JourneyHint.hint_key == hint_key)
        .first()
    )
    now = datetime.now(timezone.utc)
    snooze_until = now + timedelta(days=7)
    if existing:
        existing.status = "snoozed"
        existing.snoozed_until = snooze_until
    else:
        db.add(JourneyHint(user_id=user_id, hint_key=hint_key, status="snoozed", snoozed_until=snooze_until))
    db.commit()


def suppress_all_hints(db: Session, user_id: int) -> None:
    """Suppress ALL hints for a user (nuclear option)."""
    existing = (
        db.query(JourneyHint)
        .filter(JourneyHint.user_id == user_id, JourneyHint.hint_key == "__all__")
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.status = "suppressed"
        existing.dismissed_at = now
    else:
        db.add(JourneyHint(user_id=user_id, hint_key="__all__", status="suppressed", dismissed_at=now))
    db.commit()
