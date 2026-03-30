"""Tests for the journey hint detection service."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Helpers — use lazy imports so conftest's app fixture initialises models first
# ---------------------------------------------------------------------------

PASSWORD = "Password123!"


def _make_user(db: Session, role, **overrides):
    """Create and persist a user with sensible defaults."""
    from app.models.user import User
    now = datetime.now(timezone.utc)
    defaults = {
        "email": f"hint-{role.value}-{uuid.uuid4().hex[:8]}@example.com",
        "full_name": f"Test {role.value.title()}",
        "hashed_password": "x",
        "role": role,
        "roles": role.value,
        "is_active": True,
        "created_at": now - timedelta(days=1),  # fresh account
    }
    defaults.update(overrides)
    user = User(**defaults)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHintForNewParentNoChildren:
    """A brand-new parent with no children should see a hint."""

    def test_returns_hint_on_dashboard(self, db_session: Session):
        from app.models.user import UserRole
        from app.services.journey_hint_service import get_hint_for_user

        user = _make_user(db_session, UserRole.PARENT)
        result = get_hint_for_user(db_session, user, "dashboard")
        # First hint for a brand-new user with no journey_hints rows = welcome_modal
        assert result is not None
        assert result["hint_key"] == "welcome_modal"

    def test_returns_add_child_after_welcome(self, db_session: Session):
        from app.models.user import UserRole
        from app.services.journey_hint_service import dismiss_hint, get_hint_for_user

        user = _make_user(db_session, UserRole.PARENT)
        # Simulate welcome already dismissed
        dismiss_hint(db_session, user.id, "welcome_modal")
        # With 1 dismissal we are still under the limit of 2
        result = get_hint_for_user(db_session, user, "dashboard")
        assert result is not None
        assert result["hint_key"] == "parent.add_child"


class TestHintNotReturnedWhenParentHasChildren:
    """When parent already linked a child, add_child hint should not fire."""

    def test_no_add_child_hint(self, db_session: Session):
        from app.models.user import UserRole
        from app.models.student import Student, parent_students
        from app.services.journey_hint_service import dismiss_hint, get_hint_for_user

        user = _make_user(db_session, UserRole.PARENT)
        # Dismiss welcome so add_child is next candidate
        dismiss_hint(db_session, user.id, "welcome_modal")
        # Create a student and link
        student_user = _make_user(db_session, UserRole.STUDENT, email="child-linked@example.com")
        student = Student(user_id=student_user.id, grade_level=8)
        db_session.add(student)
        db_session.commit()
        db_session.refresh(student)
        db_session.execute(parent_students.insert().values(
            parent_id=user.id, student_id=student.id,
        ))
        db_session.commit()

        result = get_hint_for_user(db_session, user, "my-kids")
        # Should not be add_child — it should be something else or None
        if result is not None:
            assert result["hint_key"] != "parent.add_child"


class TestHintNotReturnedAfterDismiss:
    """Dismissed hints should never reappear."""

    def test_dismissed_hint_skipped(self, db_session: Session):
        from app.models.user import UserRole
        from app.services.journey_hint_service import dismiss_hint, get_hint_for_user

        user = _make_user(db_session, UserRole.PARENT)
        dismiss_hint(db_session, user.id, "welcome_modal")
        dismiss_hint(db_session, user.id, "parent.add_child")
        # With 2 dismissals in 14 days, the frequency cap kicks in
        result = get_hint_for_user(db_session, user, "dashboard")
        assert result is None


class TestHintNotReturnedAfter30DayAccountAge:
    """Accounts older than 30 days get no hints."""

    def test_old_account_no_hints(self, db_session: Session):
        from app.models.user import UserRole
        from app.services.journey_hint_service import get_hint_for_user

        user = _make_user(
            db_session,
            UserRole.PARENT,
            created_at=datetime.now(timezone.utc) - timedelta(days=31),
        )
        result = get_hint_for_user(db_session, user, "dashboard")
        assert result is None


class TestSuppressAllHints:
    """suppress_all permanently silences hints."""

    def test_suppress_all(self, db_session: Session):
        from app.models.user import UserRole
        from app.services.journey_hint_service import suppress_all_hints, get_hint_for_user

        user = _make_user(db_session, UserRole.PARENT)
        suppress_all_hints(db_session, user.id)
        result = get_hint_for_user(db_session, user, "dashboard")
        assert result is None


class TestMaxOneHintPerDay:
    """Only one hint per day should be shown."""

    def test_one_per_day(self, db_session: Session):
        from app.models.user import UserRole
        from app.services.journey_hint_service import record_hint_shown, get_hint_for_user

        user = _make_user(db_session, UserRole.PARENT)
        # Record that a hint was shown today
        record_hint_shown(db_session, user.id, "welcome_modal")
        result = get_hint_for_user(db_session, user, "dashboard")
        assert result is None


class TestSnoozeHint:
    """Snoozed hints should not appear until snooze expires."""

    def test_snoozed_hint_skipped(self, db_session: Session):
        from app.models.user import UserRole
        from app.services.journey_hint_service import snooze_hint, get_hint_for_user

        user = _make_user(db_session, UserRole.STUDENT)
        # Snooze welcome_modal
        snooze_hint(db_session, user.id, "welcome_modal", days=7)
        result = get_hint_for_user(db_session, user, "study-hub")
        # welcome_modal is snoozed, so the next applicable hint is returned instead
        if result is not None:
            assert result["hint_key"] != "welcome_modal"


class TestRecordHintShown:
    """record_hint_shown persists a row."""

    def test_creates_row(self, db_session: Session):
        from app.models.user import UserRole
        from app.services.journey_hint_service import JourneyHint, record_hint_shown

        user = _make_user(db_session, UserRole.TEACHER)
        record_hint_shown(db_session, user.id, "teacher.create_course")
        row = db_session.query(JourneyHint).filter(
            JourneyHint.user_id == user.id,
            JourneyHint.hint_key == "teacher.create_course",
        ).first()
        assert row is not None
        assert row.status == "shown"
