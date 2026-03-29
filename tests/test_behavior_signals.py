"""
Tests for behaviour signal detection in journey hints (#2609).
"""
from datetime import datetime, timedelta, timezone

import pytest

from conftest import PASSWORD


@pytest.fixture()
def signal_user(db_session):
    """Create a fresh test user for behaviour-signal tests."""
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash
    from app.models.journey_hint import JourneyHint
    from app.models.audit_log import AuditLog

    hashed = get_password_hash(PASSWORD)

    user = db_session.query(User).filter(User.email == "signal_user@test.com").first()
    if not user:
        user = User(
            email="signal_user@test.com",
            username="signal_user",
            hashed_password=hashed,
            full_name="Signal User",
            role=UserRole.PARENT,
            roles="parent",
            onboarding_completed=True,
            email_verified=True,
            # New account — less than 30 days old
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        db_session.add(user)
        db_session.flush()

    # Clean up prior hint and audit data for this user
    db_session.query(JourneyHint).filter(JourneyHint.user_id == user.id).delete()
    db_session.query(AuditLog).filter(AuditLog.user_id == user.id).delete()
    db_session.commit()

    return user


# ── Nuclear suppress ────────────────────────────────────────────────


def test_nuclear_suppress_blocks_all_hints(db_session, signal_user):
    from app.models.journey_hint import JourneyHint
    from app.services.journey_hint_service import check_behavior_signals

    # No suppress flag → hints allowed
    assert check_behavior_signals(db_session, signal_user.id) is False

    # Add nuclear suppress
    db_session.add(
        JourneyHint(
            user_id=signal_user.id,
            hint_key="suppress_all",
            status="shown",
        )
    )
    db_session.flush()

    assert check_behavior_signals(db_session, signal_user.id) is True


# ── Two-strike cooldown ────────────────────────────────────────────


def test_two_strike_cooldown_triggers(db_session, signal_user):
    from app.models.journey_hint import JourneyHint
    from app.services.journey_hint_service import check_behavior_signals

    # One dismissal — not enough
    db_session.add(
        JourneyHint(
            user_id=signal_user.id,
            hint_key="hint_a",
            status="dismissed",
            engaged=False,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    db_session.flush()
    assert check_behavior_signals(db_session, signal_user.id) is False

    # Second consecutive dismissal → should suppress
    db_session.add(
        JourneyHint(
            user_id=signal_user.id,
            hint_key="hint_b",
            status="dismissed",
            engaged=False,
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.flush()
    assert check_behavior_signals(db_session, signal_user.id) is True


def test_cooldown_resets_on_engagement(db_session, signal_user):
    from app.models.journey_hint import JourneyHint
    from app.services.journey_hint_service import check_behavior_signals

    # Dismissed, then engaged, then dismissed — only 1 consecutive → allowed
    now = datetime.now(timezone.utc)
    for i, (status, engaged) in enumerate(
        [("dismissed", False), ("engaged", True), ("dismissed", False)]
    ):
        db_session.add(
            JourneyHint(
                user_id=signal_user.id,
                hint_key=f"hint_{i}",
                status=status,
                engaged=engaged,
                created_at=now - timedelta(hours=3 - i),
            )
        )
    db_session.flush()

    # Most recent is 1 dismissal, then an engagement breaks the streak
    assert check_behavior_signals(db_session, signal_user.id) is False


# ── Self-directed user ──────────────────────────────────────────────


def test_self_directed_user_suppresses(db_session, signal_user):
    from app.models.audit_log import AuditLog
    from app.services.journey_hint_service import check_behavior_signals

    assert check_behavior_signals(db_session, signal_user.id) is False

    db_session.add(
        AuditLog(
            user_id=signal_user.id,
            action="page_view_help",
            resource_type="page",
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
    )
    db_session.flush()

    assert check_behavior_signals(db_session, signal_user.id) is True


def test_old_help_visit_does_not_suppress(db_session, signal_user):
    from app.models.audit_log import AuditLog
    from app.services.journey_hint_service import check_behavior_signals

    # Help page visit 10 days ago — outside 7-day window
    db_session.add(
        AuditLog(
            user_id=signal_user.id,
            action="page_view_help",
            resource_type="page",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
    )
    db_session.flush()

    assert check_behavior_signals(db_session, signal_user.id) is False


# ── Account age ─────────────────────────────────────────────────────


def test_account_age_suppresses_after_30_days(db_session, signal_user):
    from app.services.journey_hint_service import check_behavior_signals

    # Default fixture user is 5 days old → allowed
    assert check_behavior_signals(db_session, signal_user.id) is False

    # Make account old
    signal_user.created_at = datetime.now(timezone.utc) - timedelta(days=35)
    db_session.flush()

    assert check_behavior_signals(db_session, signal_user.id) is True


# ── Engagement recording ────────────────────────────────────────────


def test_record_hint_engagement_creates_entry(db_session, signal_user):
    from app.models.journey_hint import JourneyHint
    from app.services.journey_hint_service import record_hint_engagement

    record_hint_engagement(db_session, signal_user.id, "test_hint", engaged=True)
    db_session.commit()

    entry = (
        db_session.query(JourneyHint)
        .filter(
            JourneyHint.user_id == signal_user.id,
            JourneyHint.hint_key == "test_hint",
        )
        .first()
    )
    assert entry is not None
    assert entry.engaged is True
    assert entry.status == "engaged"


def test_record_hint_engagement_updates_existing(db_session, signal_user):
    from app.models.journey_hint import JourneyHint
    from app.services.journey_hint_service import record_hint_engagement

    # Create an initial "shown" entry
    db_session.add(
        JourneyHint(
            user_id=signal_user.id,
            hint_key="update_hint",
            status="shown",
        )
    )
    db_session.flush()

    # Record dismissal
    record_hint_engagement(db_session, signal_user.id, "update_hint", engaged=False)
    db_session.flush()

    entry = (
        db_session.query(JourneyHint)
        .filter(
            JourneyHint.user_id == signal_user.id,
            JourneyHint.hint_key == "update_hint",
        )
        .first()
    )
    assert entry.engaged is False
    assert entry.status == "dismissed"
