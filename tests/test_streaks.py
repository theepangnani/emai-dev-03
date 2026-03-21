"""
Tests for the Streak Engine (#2002, #2003).
"""
from datetime import date, datetime, timedelta

import pytest

from conftest import PASSWORD, _auth


@pytest.fixture()
def streak_student(db_session):
    """Create or retrieve a test student for streak tests."""
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash

    hashed = get_password_hash(PASSWORD)
    student = db_session.query(User).filter(User.email == "streak_student@test.com").first()
    if not student:
        student = User(
            email="streak_student@test.com",
            username="streak_student",
            hashed_password=hashed,
            full_name="Streak Student",
            role=UserRole.STUDENT,
            roles="student",
            onboarding_completed=True,
            email_verified=True,
        )
        db_session.add(student)
        db_session.commit()
    return student


@pytest.fixture()
def clean_streak_data(db_session, streak_student):
    """Clean streak data before each test for isolation."""
    from app.models.xp import StreakLog, XpSummary

    db_session.query(StreakLog).filter(StreakLog.student_id == streak_student.id).delete()
    db_session.query(XpSummary).filter(XpSummary.student_id == streak_student.id).delete()
    db_session.commit()
    return streak_student


# ── Tier calculation tests ──────────────────────────────────────────


class TestStreakTier:
    def test_grey_tier(self, app):
        from app.services.streak_service import StreakService

        tier = StreakService.get_streak_tier(0)
        assert tier["tier"] == "grey"
        assert tier["multiplier"] == 1.0

    def test_orange_tier(self, app):
        from app.services.streak_service import StreakService

        tier = StreakService.get_streak_tier(7)
        assert tier["tier"] == "orange"
        assert tier["multiplier"] == 1.25

    def test_red_tier(self, app):
        from app.services.streak_service import StreakService

        tier = StreakService.get_streak_tier(14)
        assert tier["tier"] == "red"
        assert tier["multiplier"] == 1.5

    def test_red_glow_tier(self, app):
        from app.services.streak_service import StreakService

        tier = StreakService.get_streak_tier(30)
        assert tier["tier"] == "red_glow"
        assert tier["multiplier"] == 1.75

    def test_gold_tier(self, app):
        from app.services.streak_service import StreakService

        tier = StreakService.get_streak_tier(60)
        assert tier["tier"] == "gold"
        assert tier["multiplier"] == 2.0

    def test_boundary_values(self, app):
        from app.services.streak_service import StreakService

        assert StreakService.get_streak_tier(6)["tier"] == "grey"
        assert StreakService.get_streak_tier(7)["tier"] == "orange"
        assert StreakService.get_streak_tier(13)["tier"] == "orange"
        assert StreakService.get_streak_tier(14)["tier"] == "red"
        assert StreakService.get_streak_tier(29)["tier"] == "red"
        assert StreakService.get_streak_tier(30)["tier"] == "red_glow"
        assert StreakService.get_streak_tier(59)["tier"] == "red_glow"
        assert StreakService.get_streak_tier(60)["tier"] == "gold"


# ── Recording qualifying actions ────────────────────────────────────


class TestRecordQualifyingAction:
    def test_first_action_starts_streak(self, db_session, clean_streak_data):
        from app.services.streak_service import StreakService
        from app.models.xp import XpSummary

        student = clean_streak_data
        log = StreakService.record_qualifying_action(db_session, student.id, "study_guide")

        assert log is not None
        assert log.qualifying_action == "study_guide"
        assert log.log_date == date.today()
        assert log.streak_value == 1

        summary = db_session.query(XpSummary).filter(XpSummary.student_id == student.id).first()
        assert summary.current_streak == 1
        assert summary.longest_streak == 1

    def test_duplicate_action_same_day(self, db_session, clean_streak_data):
        from app.services.streak_service import StreakService

        student = clean_streak_data
        log1 = StreakService.record_qualifying_action(db_session, student.id, "study_guide")
        log2 = StreakService.record_qualifying_action(db_session, student.id, "quiz")

        # Should return the existing log, not create a new one
        assert log1.id == log2.id

    def test_consecutive_days_increment_streak(self, db_session, clean_streak_data):
        from app.services.streak_service import StreakService
        from app.models.xp import XpSummary, StreakLog

        student = clean_streak_data

        # Simulate yesterday's action by creating a log entry manually
        yesterday = date.today() - timedelta(days=1)
        summary = StreakService._get_or_create_summary(db_session, student.id)
        summary.current_streak = 1
        summary.longest_streak = 1
        summary.last_streak_date = yesterday
        yesterday_log = StreakLog(
            student_id=student.id,
            log_date=yesterday,
            qualifying_action="quiz",
            streak_value=1,
            multiplier=1.0,
        )
        db_session.add(yesterday_log)
        db_session.commit()

        # Now record today's action
        log = StreakService.record_qualifying_action(db_session, student.id, "study_guide")

        assert log.streak_value == 2
        db_session.refresh(summary)
        assert summary.current_streak == 2
        assert summary.longest_streak == 2


# ── Streak evaluation (nightly cron) ────────────────────────────────


class TestEvaluateStreak:
    def test_active_streak_continues(self, db_session, clean_streak_data):
        from app.services.streak_service import StreakService
        from app.models.xp import XpSummary, StreakLog

        student = clean_streak_data
        yesterday = date.today() - timedelta(days=1)

        # Set up active streak with yesterday's log
        summary = StreakService._get_or_create_summary(db_session, student.id)
        summary.current_streak = 5
        summary.longest_streak = 5
        summary.last_streak_date = yesterday
        db_session.add(StreakLog(
            student_id=student.id,
            log_date=yesterday,
            qualifying_action="quiz",
            streak_value=5,
            multiplier=1.25,
        ))
        db_session.commit()

        result = StreakService.evaluate_streak(db_session, student.id)
        assert result == "active"

    def test_streak_breaks_on_miss(self, db_session, clean_streak_data):
        from app.services.streak_service import StreakService
        from app.models.xp import XpSummary

        student = clean_streak_data
        two_days_ago = date.today() - timedelta(days=2)

        # Set up streak but no activity yesterday
        summary = StreakService._get_or_create_summary(db_session, student.id)
        summary.current_streak = 5
        summary.longest_streak = 5
        summary.last_streak_date = two_days_ago
        summary.freeze_tokens_remaining = 0
        db_session.commit()

        result = StreakService.evaluate_streak(db_session, student.id)
        assert result == "broken"

        db_session.refresh(summary)
        assert summary.current_streak == 0
        assert summary.streak_broken_at is not None

    def test_holiday_preserves_streak(self, db_session, clean_streak_data):
        from app.services.streak_service import StreakService
        from app.models.xp import XpSummary
        from app.models.holiday import HolidayDate

        student = clean_streak_data
        yesterday = date.today() - timedelta(days=1)

        # Add yesterday as a holiday
        existing_holiday = db_session.query(HolidayDate).filter(
            HolidayDate.date == yesterday
        ).first()
        if not existing_holiday:
            db_session.add(HolidayDate(date=yesterday, name="Test Holiday"))
            db_session.commit()

        # Set up streak but no activity yesterday
        summary = StreakService._get_or_create_summary(db_session, student.id)
        summary.current_streak = 5
        summary.longest_streak = 5
        summary.last_streak_date = date.today() - timedelta(days=2)
        summary.freeze_tokens_remaining = 0
        db_session.commit()

        result = StreakService.evaluate_streak(db_session, student.id)
        assert result == "holiday"

        db_session.refresh(summary)
        assert summary.current_streak == 5  # Preserved

        # Clean up holiday
        db_session.query(HolidayDate).filter(HolidayDate.date == yesterday).delete()
        db_session.commit()

    def test_freeze_token_preserves_streak(self, db_session, clean_streak_data):
        from app.services.streak_service import StreakService
        from app.models.xp import XpSummary

        student = clean_streak_data
        two_days_ago = date.today() - timedelta(days=2)

        # Set up streak with freeze token but no activity yesterday
        summary = StreakService._get_or_create_summary(db_session, student.id)
        summary.current_streak = 5
        summary.longest_streak = 5
        summary.last_streak_date = two_days_ago
        summary.freeze_tokens_remaining = 1
        db_session.commit()

        result = StreakService.evaluate_streak(db_session, student.id)
        assert result == "frozen"

        db_session.refresh(summary)
        assert summary.current_streak == 5  # Preserved
        assert summary.freeze_tokens_remaining == 0  # Used up


# ── Monthly freeze token refresh ────────────────────────────────────


class TestFreezeTokenRefresh:
    def test_refresh_resets_all_tokens(self, db_session, clean_streak_data):
        from app.services.streak_service import StreakService
        from app.models.xp import XpSummary

        student = clean_streak_data

        # Set up summary with 0 tokens
        summary = StreakService._get_or_create_summary(db_session, student.id)
        summary.freeze_tokens_remaining = 0
        db_session.commit()

        count = StreakService.refresh_monthly_freeze_tokens(db_session)
        assert count >= 1

        db_session.refresh(summary)
        assert summary.freeze_tokens_remaining == 1


# ── Streak recovery ─────────────────────────────────────────────────


class TestStreakRecovery:
    def test_eligible_within_24_hours(self, db_session, clean_streak_data):
        from app.services.streak_service import StreakService
        from app.models.xp import XpSummary

        student = clean_streak_data

        summary = StreakService._get_or_create_summary(db_session, student.id)
        summary.current_streak = 0
        summary.longest_streak = 10
        summary.streak_broken_at = datetime.utcnow() - timedelta(hours=12)
        summary.last_recovery_at = None
        db_session.commit()

        info = StreakService.check_streak_recovery(db_session, student.id)
        assert info is not None
        assert info["eligible"] is True

    def test_not_eligible_after_24_hours(self, db_session, clean_streak_data):
        from app.services.streak_service import StreakService
        from app.models.xp import XpSummary

        student = clean_streak_data

        summary = StreakService._get_or_create_summary(db_session, student.id)
        summary.current_streak = 0
        summary.streak_broken_at = datetime.utcnow() - timedelta(hours=25)
        summary.last_recovery_at = None
        db_session.commit()

        info = StreakService.check_streak_recovery(db_session, student.id)
        assert info is None

    def test_not_eligible_if_recently_recovered(self, db_session, clean_streak_data):
        from app.services.streak_service import StreakService
        from app.models.xp import XpSummary

        student = clean_streak_data

        summary = StreakService._get_or_create_summary(db_session, student.id)
        summary.current_streak = 0
        summary.streak_broken_at = datetime.utcnow() - timedelta(hours=6)
        summary.last_recovery_at = datetime.utcnow() - timedelta(days=10)
        db_session.commit()

        info = StreakService.check_streak_recovery(db_session, student.id)
        assert info is None

    def test_recover_restores_streak(self, db_session, clean_streak_data):
        from app.services.streak_service import StreakService
        from app.models.xp import XpSummary, StreakLog

        student = clean_streak_data

        # Create a log entry to restore from
        db_session.add(StreakLog(
            student_id=student.id,
            log_date=date.today() - timedelta(days=2),
            qualifying_action="quiz",
            streak_value=8,
            multiplier=1.25,
        ))
        db_session.commit()

        summary = StreakService._get_or_create_summary(db_session, student.id)
        summary.current_streak = 0
        summary.longest_streak = 8
        summary.streak_broken_at = datetime.utcnow() - timedelta(hours=6)
        summary.last_recovery_at = None
        db_session.commit()

        result = StreakService.recover_streak(db_session, student.id)
        assert result is not None
        assert result["recovered"] is True
        assert result["current_streak"] == 8

        db_session.refresh(summary)
        assert summary.current_streak == 8
        assert summary.streak_broken_at is None
        assert summary.last_recovery_at is not None


# ── API endpoint tests ──────────────────────────────────────────────


class TestStreakAPI:
    def test_get_streak_info(self, client, db_session, streak_student):
        headers = _auth(client, "streak_student@test.com")
        resp = client.get("/api/xp/streak", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "current_streak" in data
        assert "longest_streak" in data
        assert "freeze_tokens_remaining" in data
        assert "streak_tier" in data
        assert "multiplier" in data

    def test_recover_streak_not_eligible(self, client, db_session, streak_student):
        headers = _auth(client, "streak_student@test.com")
        resp = client.post("/api/xp/streak/recover", headers=headers)
        assert resp.status_code == 400
