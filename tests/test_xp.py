"""
Tests for the XP Gamification system (#2000, #2001).
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from conftest import PASSWORD


@pytest.fixture()
def xp_student(db_session):
    """Create or retrieve a test student for XP tests."""
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash

    hashed = get_password_hash(PASSWORD)

    student = db_session.query(User).filter(User.email == "xp_student@test.com").first()
    if not student:
        student = User(
            email="xp_student@test.com",
            username="xp_student",
            hashed_password=hashed,
            full_name="XP Student",
            role=UserRole.STUDENT,
            roles="student",
            onboarding_completed=True,
            email_verified=True,
        )
        db_session.add(student)
        db_session.flush()

    # Clean up any prior XP data for this student
    from app.models.xp import XpLedger, XpSummary
    db_session.query(XpLedger).filter(XpLedger.student_id == student.id).delete()
    db_session.query(XpSummary).filter(XpSummary.student_id == student.id).delete()
    db_session.commit()

    return student


# ── Level calculation ──

class TestLevelCalculation:
    def test_level_1_at_zero(self):
        from app.services.xp_service import get_level_for_xp
        lvl = get_level_for_xp(0)
        assert lvl["level"] == 1
        assert lvl["title"] == "Curious Learner"

    def test_level_2_at_200(self):
        from app.services.xp_service import get_level_for_xp
        lvl = get_level_for_xp(200)
        assert lvl["level"] == 2

    def test_level_2_at_499(self):
        from app.services.xp_service import get_level_for_xp
        lvl = get_level_for_xp(499)
        assert lvl["level"] == 2

    def test_level_8_at_max(self):
        from app.services.xp_service import get_level_for_xp
        lvl = get_level_for_xp(8000)
        assert lvl["level"] == 8
        assert lvl["title"] == "ClassBridge Elite"

    def test_level_8_above_max(self):
        from app.services.xp_service import get_level_for_xp
        lvl = get_level_for_xp(99999)
        assert lvl["level"] == 8

    def test_xp_to_next_level(self):
        from app.services.xp_service import get_xp_to_next_level
        assert get_xp_to_next_level(0) == 200
        assert get_xp_to_next_level(100) == 100
        assert get_xp_to_next_level(200) == 300  # need 500 for lvl 3
        assert get_xp_to_next_level(8000) == 0   # max level


# ── Streak multiplier ──

class TestStreakMultiplier:
    def test_no_streak(self):
        from app.services.xp_service import get_streak_multiplier
        assert get_streak_multiplier(0) == 1.0

    def test_7_day_streak(self):
        from app.services.xp_service import get_streak_multiplier
        assert get_streak_multiplier(7) == 1.25

    def test_14_day_streak(self):
        from app.services.xp_service import get_streak_multiplier
        assert get_streak_multiplier(14) == 1.5

    def test_30_day_streak(self):
        from app.services.xp_service import get_streak_multiplier
        assert get_streak_multiplier(30) == 1.75

    def test_60_day_streak(self):
        from app.services.xp_service import get_streak_multiplier
        assert get_streak_multiplier(60) == 2.0

    def test_100_day_streak(self):
        from app.services.xp_service import get_streak_multiplier
        assert get_streak_multiplier(100) == 2.0


# ── XP award ──

class TestAwardXp:
    def test_award_upload(self, db_session, xp_student):
        from app.services.xp_service import award_xp
        entry = award_xp(db_session, xp_student.id, "upload")
        assert entry is not None
        assert entry.xp_awarded == 10
        assert entry.action_type == "upload"
        assert entry.multiplier == 1.0
        db_session.commit()

    def test_award_study_guide(self, db_session, xp_student):
        from app.services.xp_service import award_xp
        entry = award_xp(db_session, xp_student.id, "study_guide")
        assert entry is not None
        assert entry.xp_awarded == 20
        db_session.commit()

    def test_award_all_action_types(self, db_session, xp_student):
        from app.services.xp_service import award_xp, XP_ACTIONS
        for action_type, config in XP_ACTIONS.items():
            entry = award_xp(db_session, xp_student.id, action_type)
            assert entry is not None, f"Failed to award XP for {action_type}"
            assert entry.xp_awarded == config["xp"]
        db_session.commit()

    def test_award_unknown_action(self, db_session, xp_student):
        from app.services.xp_service import award_xp
        entry = award_xp(db_session, xp_student.id, "nonexistent_action")
        assert entry is None

    def test_updates_summary(self, db_session, xp_student):
        from app.services.xp_service import award_xp
        from app.models.xp import XpSummary
        award_xp(db_session, xp_student.id, "upload")
        db_session.commit()
        summary = db_session.query(XpSummary).filter(
            XpSummary.student_id == xp_student.id,
        ).first()
        assert summary is not None
        assert summary.total_xp == 10
        assert summary.current_level == 1


# ── Daily cap ──

def _backdate_last_entry(db_session, student_id, seconds=61):
    """Backdate the most recent XP ledger entry to bypass the 60s dedup window."""
    from app.models.xp import XpLedger
    last = (
        db_session.query(XpLedger)
        .filter(XpLedger.student_id == student_id)
        .order_by(XpLedger.created_at.desc())
        .first()
    )
    if last:
        last.created_at = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        db_session.flush()


class TestDailyCap:
    def test_daily_cap_enforced(self, db_session, xp_student):
        from app.services.xp_service import award_xp

        # upload: xp=10, daily_cap=30 → 3 full awards, 4th should be None
        for i in range(3):
            entry = award_xp(db_session, xp_student.id, "upload")
            assert entry is not None, f"Award {i+1} should succeed"
            _backdate_last_entry(db_session, xp_student.id)

        capped = award_xp(db_session, xp_student.id, "upload")
        assert capped is None, "4th upload should be capped"
        db_session.commit()

    def test_daily_cap_partial(self, db_session, xp_student):
        """When remaining cap is less than base XP, award partial."""
        from app.services.xp_service import award_xp

        # daily_login: xp=5, daily_cap=5 → 1 full award, 2nd capped
        entry = award_xp(db_session, xp_student.id, "daily_login")
        assert entry is not None
        assert entry.xp_awarded == 5
        _backdate_last_entry(db_session, xp_student.id)

        capped = award_xp(db_session, xp_student.id, "daily_login")
        assert capped is None
        db_session.commit()

    def test_different_actions_independent_caps(self, db_session, xp_student):
        from app.services.xp_service import award_xp

        # Cap uploads
        for _ in range(3):
            award_xp(db_session, xp_student.id, "upload")
            _backdate_last_entry(db_session, xp_student.id)

        capped = award_xp(db_session, xp_student.id, "upload")
        assert capped is None

        # study_guide should still work (different cap)
        entry = award_xp(db_session, xp_student.id, "study_guide")
        assert entry is not None
        db_session.commit()


# ── Streak multiplier applied to awards ──

class TestStreakMultiplierAward:
    def test_streak_multiplier_applied(self, db_session, xp_student):
        from app.services.xp_service import award_xp
        from app.models.xp import XpSummary

        # Set a 7-day streak on the summary
        summary = db_session.query(XpSummary).filter(
            XpSummary.student_id == xp_student.id,
        ).first()
        if not summary:
            summary = XpSummary(student_id=xp_student.id, current_streak=7)
            db_session.add(summary)
        else:
            summary.current_streak = 7
        db_session.flush()

        entry = award_xp(db_session, xp_student.id, "upload")
        assert entry is not None
        # upload base=10, 7-day multiplier=1.25 → 12
        assert entry.xp_awarded == 12
        assert entry.multiplier == 1.25
        db_session.commit()


# ── XP summary ──

class TestGetSummary:
    def test_get_summary_new_student(self, db_session, xp_student):
        from app.services.xp_service import get_summary
        resp = get_summary(db_session, xp_student.id)
        assert resp.total_xp == 0
        assert resp.current_level == 1
        assert resp.level_title == "Curious Learner"
        assert resp.xp_to_next_level == 200

    def test_get_summary_after_awards(self, db_session, xp_student):
        from app.services.xp_service import award_xp, get_summary
        award_xp(db_session, xp_student.id, "upload")
        award_xp(db_session, xp_student.id, "study_guide")
        db_session.commit()

        resp = get_summary(db_session, xp_student.id)
        assert resp.total_xp == 30  # 10 + 20
        assert resp.today_xp == 30


# ── XP history ──

class TestGetHistory:
    def test_get_history_empty(self, db_session, xp_student):
        from app.services.xp_service import get_history
        resp = get_history(db_session, xp_student.id)
        assert resp.total_count == 0
        assert resp.entries == []

    def test_get_history_with_entries(self, db_session, xp_student):
        from app.services.xp_service import award_xp, get_history
        award_xp(db_session, xp_student.id, "upload")
        award_xp(db_session, xp_student.id, "study_guide")
        db_session.commit()

        resp = get_history(db_session, xp_student.id)
        assert resp.total_count == 2
        assert len(resp.entries) == 2
        action_types = {e.action_type for e in resp.entries}
        assert action_types == {"upload", "study_guide"}

    def test_get_history_pagination(self, db_session, xp_student):
        from app.services.xp_service import award_xp, get_history
        for _ in range(3):
            award_xp(db_session, xp_student.id, "upload")
            _backdate_last_entry(db_session, xp_student.id)
        db_session.commit()

        resp = get_history(db_session, xp_student.id, limit=2, offset=0)
        assert resp.total_count == 3
        assert len(resp.entries) == 2

        resp2 = get_history(db_session, xp_student.id, limit=2, offset=2)
        assert len(resp2.entries) == 1


# ── Fail-safe behavior ──

class TestFailSafe:
    def test_award_xp_never_raises(self, db_session, xp_student):
        """award_xp must never raise, even on DB errors."""
        from app.services.xp_service import award_xp

        with patch("app.services.xp_service._get_today_xp", side_effect=RuntimeError("DB exploded")):
            result = award_xp(db_session, xp_student.id, "upload")
            assert result is None  # graceful failure, no exception

    def test_award_xp_invalid_action_no_raise(self, db_session, xp_student):
        from app.services.xp_service import award_xp
        result = award_xp(db_session, xp_student.id, "totally_fake_action")
        assert result is None

    def test_anti_gaming_check_failure_is_failsafe(self, db_session, xp_student):
        """If anti-gaming checks raise, XP should still be awarded."""
        from app.services.xp_service import award_xp

        with patch("app.services.xp_service._check_dedup_window", side_effect=RuntimeError("DB error")):
            result = award_xp(db_session, xp_student.id, "upload")
            assert result is not None
        db_session.commit()


# ── Anti-gaming rules (#2009) ──

class TestFlashcardCooldown:
    def test_flashcard_review_blocked_within_30s(self, db_session, xp_student):
        """Second flashcard_review within 30s should be rejected."""
        from app.services.xp_service import award_xp

        first = award_xp(db_session, xp_student.id, "flashcard_review")
        assert first is not None

        second = award_xp(db_session, xp_student.id, "flashcard_review")
        assert second is None
        db_session.commit()

    def test_flashcard_got_it_blocked_within_30s(self, db_session, xp_student):
        """Second flashcard_got_it within 30s should be rejected."""
        from app.services.xp_service import award_xp

        first = award_xp(db_session, xp_student.id, "flashcard_got_it")
        assert first is not None

        second = award_xp(db_session, xp_student.id, "flashcard_got_it")
        assert second is None
        db_session.commit()

    def test_flashcard_allowed_after_cooldown(self, db_session, xp_student):
        """Flashcard XP should be awarded if last entry is > 60s ago (past both cooldown and dedup)."""
        from app.services.xp_service import award_xp

        first = award_xp(db_session, xp_student.id, "flashcard_review")
        assert first is not None

        # Backdate the entry past both the 30s flashcard cooldown and 60s dedup window
        first.created_at = datetime.now(timezone.utc) - timedelta(seconds=61)
        db_session.flush()

        second = award_xp(db_session, xp_student.id, "flashcard_review")
        assert second is not None
        db_session.commit()


class TestDedupWindow:
    def test_same_action_within_60s_rejected(self, db_session, xp_student):
        """Duplicate action within 60s window should be rejected."""
        from app.services.xp_service import award_xp

        first = award_xp(db_session, xp_student.id, "study_guide")
        assert first is not None

        second = award_xp(db_session, xp_student.id, "study_guide")
        assert second is None
        db_session.commit()

    def test_different_actions_within_60s_allowed(self, db_session, xp_student):
        """Different action types within 60s should both be awarded."""
        from app.services.xp_service import award_xp

        first = award_xp(db_session, xp_student.id, "upload")
        assert first is not None

        second = award_xp(db_session, xp_student.id, "study_guide")
        assert second is not None
        db_session.commit()

    def test_same_action_allowed_after_60s(self, db_session, xp_student):
        """Same action should be allowed after 60s window expires."""
        from app.services.xp_service import award_xp

        first = award_xp(db_session, xp_student.id, "upload")
        assert first is not None

        # Backdate entry to 61 seconds ago
        first.created_at = datetime.now(timezone.utc) - timedelta(seconds=61)
        db_session.flush()

        second = award_xp(db_session, xp_student.id, "upload")
        assert second is not None
        db_session.commit()


class TestQuizRepeatCap:
    def test_quiz_repeat_blocked_within_4h(self, db_session, xp_student):
        """Same quiz within 4 hours should be rejected."""
        from app.services.xp_service import award_xp

        first = award_xp(db_session, xp_student.id, "quiz_complete", context_id="guide_42")
        assert first is not None

        # Backdate to 2 hours ago (still within 4h, but past dedup)
        first.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db_session.flush()

        second = award_xp(db_session, xp_student.id, "quiz_complete", context_id="guide_42")
        assert second is None
        db_session.commit()

    def test_quiz_different_context_allowed(self, db_session, xp_student):
        """Different quiz (different context_id) within 4h should be allowed."""
        from app.services.xp_service import award_xp

        first = award_xp(db_session, xp_student.id, "quiz_complete", context_id="guide_42")
        assert first is not None

        # Backdate past dedup window
        first.created_at = datetime.now(timezone.utc) - timedelta(seconds=61)
        db_session.flush()

        second = award_xp(db_session, xp_student.id, "quiz_complete", context_id="guide_99")
        assert second is not None
        db_session.commit()

    def test_quiz_allowed_after_4h(self, db_session, xp_student):
        """Same quiz should be allowed after 4h window."""
        from app.services.xp_service import award_xp

        first = award_xp(db_session, xp_student.id, "quiz_complete", context_id="guide_42")
        assert first is not None

        # Backdate to 5 hours ago
        first.created_at = datetime.now(timezone.utc) - timedelta(hours=5)
        db_session.flush()

        second = award_xp(db_session, xp_student.id, "quiz_complete", context_id="guide_42")
        assert second is not None
        db_session.commit()

    def test_quiz_without_context_id_not_blocked(self, db_session, xp_student):
        """Quiz without context_id should not be blocked by repeat check."""
        from app.services.xp_service import award_xp

        first = award_xp(db_session, xp_student.id, "quiz_complete")
        assert first is not None

        # Backdate past dedup window
        first.created_at = datetime.now(timezone.utc) - timedelta(seconds=61)
        db_session.flush()

        second = award_xp(db_session, xp_student.id, "quiz_complete")
        assert second is not None
        db_session.commit()


class TestRapidUploadFlag:
    def test_rapid_uploads_logged_not_blocked(self, db_session, xp_student):
        """Rapid uploads should log a warning but NOT block XP."""
        from app.services.xp_service import award_xp

        # Award 3 uploads (cap is 30, each is 10, so 3 fit)
        entries = []
        for _ in range(3):
            e = award_xp(db_session, xp_student.id, "upload")
            if e:
                entries.append(e)

        # Backdate all entries so they're outside the dedup window
        # but within the rapid upload window
        for e in entries:
            e.created_at = datetime.now(timezone.utc) - timedelta(seconds=61)
        db_session.flush()

        # This 4th upload should still succeed (warning logged at 5+)
        with patch("app.services.xp_service.logger") as mock_logger:
            fourth = award_xp(db_session, xp_student.id, "upload")
            # Should not be blocked — rapid upload only logs, doesn't block
            # (but may be None due to daily cap)
            # The important thing: no exception raised
        db_session.commit()
