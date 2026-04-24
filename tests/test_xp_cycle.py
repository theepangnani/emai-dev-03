"""
Tests for short learning cycle XP awards (CB-TUTOR-002 Phase 2, #4072).

Covers per-question diminishing returns (100/70/40/0) and the 50 XP
chunk-completion bonus on top of the existing XpService primitives.
"""
import pytest

from conftest import PASSWORD


@pytest.fixture()
def cycle_student(db_session):
    """Create or retrieve a test student for cycle XP tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    hashed = get_password_hash(PASSWORD)
    student = db_session.query(User).filter(User.email == "cycle_student@test.com").first()
    if not student:
        student = User(
            email="cycle_student@test.com",
            username="cycle_student",
            hashed_password=hashed,
            full_name="Cycle Student",
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


# ── Per-question diminishing returns ──

class TestCycleQuestionXp:
    def test_attempt_1_awards_100(self, db_session, cycle_student):
        from app.services.xp_service import award_cycle_question_xp
        xp = award_cycle_question_xp(
            db_session, cycle_student.id, "q1", 1, user_role="student",
        )
        assert xp == 100
        db_session.commit()

    def test_attempt_2_awards_70(self, db_session, cycle_student):
        from app.services.xp_service import award_cycle_question_xp
        xp = award_cycle_question_xp(
            db_session, cycle_student.id, "q2", 2, user_role="student",
        )
        assert xp == 70
        db_session.commit()

    def test_attempt_3_awards_40(self, db_session, cycle_student):
        from app.services.xp_service import award_cycle_question_xp
        xp = award_cycle_question_xp(
            db_session, cycle_student.id, "q3", 3, user_role="student",
        )
        assert xp == 40
        db_session.commit()

    def test_attempt_4_awards_zero(self, db_session, cycle_student):
        """Attempts past the 3rd award 0 XP (past cap)."""
        from app.services.xp_service import award_cycle_question_xp
        xp = award_cycle_question_xp(
            db_session, cycle_student.id, "q4", 4, user_role="student",
        )
        assert xp == 0
        db_session.commit()

    def test_attempt_zero_awards_zero(self, db_session, cycle_student):
        """Attempt 0 (or negative) is defensive — awards 0."""
        from app.services.xp_service import award_cycle_question_xp
        assert award_cycle_question_xp(
            db_session, cycle_student.id, "q5", 0, user_role="student",
        ) == 0
        assert award_cycle_question_xp(
            db_session, cycle_student.id, "q5", -1, user_role="student",
        ) == 0
        db_session.commit()

    def test_double_award_same_question_dedupes(self, db_session, cycle_student):
        """Second award for the same question_id returns 0 (context_id dedup)."""
        from app.services.xp_service import award_cycle_question_xp

        first = award_cycle_question_xp(
            db_session, cycle_student.id, "q_dup", 1, user_role="student",
        )
        assert first == 100

        second = award_cycle_question_xp(
            db_session, cycle_student.id, "q_dup", 2, user_role="student",
        )
        assert second == 0, "Same question_id must not award twice"
        db_session.commit()

    def test_different_questions_both_award(self, db_session, cycle_student):
        """Different question_ids both award (dedup is per question)."""
        from app.services.xp_service import award_cycle_question_xp

        first = award_cycle_question_xp(
            db_session, cycle_student.id, "q_a", 1, user_role="student",
        )
        second = award_cycle_question_xp(
            db_session, cycle_student.id, "q_b", 1, user_role="student",
        )
        assert first == 100
        assert second == 100
        db_session.commit()

    def test_ledger_entry_fields(self, db_session, cycle_student):
        """Ledger row written with the expected action_type + context_id."""
        from app.models.xp import XpLedger
        from app.services.xp_service import award_cycle_question_xp

        award_cycle_question_xp(
            db_session, cycle_student.id, "q_fields", 1, user_role="student",
        )
        db_session.commit()

        entry = (
            db_session.query(XpLedger)
            .filter(XpLedger.student_id == cycle_student.id)
            .first()
        )
        assert entry is not None
        assert entry.action_type == "cycle_question_correct"
        assert entry.xp_awarded == 100
        assert entry.context_id == "cycle_question_q_fields"

    def test_summary_updated(self, db_session, cycle_student):
        """XpSummary.total_xp reflects the awarded XP."""
        from app.models.xp import XpSummary
        from app.services.xp_service import award_cycle_question_xp

        award_cycle_question_xp(
            db_session, cycle_student.id, "q_sum", 1, user_role="student",
        )
        db_session.commit()

        summary = (
            db_session.query(XpSummary)
            .filter(XpSummary.student_id == cycle_student.id)
            .first()
        )
        assert summary is not None
        assert summary.total_xp == 100


# ── Chunk bonus ──

class TestCycleChunkBonus:
    def test_chunk_bonus_awards_50(self, db_session, cycle_student):
        from app.services.xp_service import award_cycle_chunk_bonus
        xp = award_cycle_chunk_bonus(
            db_session, cycle_student.id, "chunk_1", user_role="student",
        )
        assert xp == 50
        db_session.commit()

    def test_chunk_bonus_dedupes(self, db_session, cycle_student):
        """Same chunk awards bonus only once."""
        from app.services.xp_service import award_cycle_chunk_bonus

        first = award_cycle_chunk_bonus(
            db_session, cycle_student.id, "chunk_dup", user_role="student",
        )
        assert first == 50

        second = award_cycle_chunk_bonus(
            db_session, cycle_student.id, "chunk_dup", user_role="student",
        )
        assert second == 0
        db_session.commit()

    def test_chunk_bonus_ledger_fields(self, db_session, cycle_student):
        from app.models.xp import XpLedger
        from app.services.xp_service import award_cycle_chunk_bonus

        award_cycle_chunk_bonus(
            db_session, cycle_student.id, "chunk_fields", user_role="student",
        )
        db_session.commit()

        entry = (
            db_session.query(XpLedger)
            .filter(
                XpLedger.student_id == cycle_student.id,
                XpLedger.action_type == "cycle_chunk_bonus",
            )
            .first()
        )
        assert entry is not None
        assert entry.xp_awarded == 50
        assert entry.context_id == "cycle_chunk_bonus_chunk_fields"


# ── Streak multiplier applied on top ──

class TestCycleStreakMultiplier:
    def test_question_streak_multiplier_applied(self, db_session, cycle_student):
        """7-day streak multiplier (1.25) applies to cycle question XP."""
        from app.models.xp import XpSummary
        from app.services.xp_service import award_cycle_question_xp

        summary = XpSummary(student_id=cycle_student.id, current_streak=7)
        db_session.add(summary)
        db_session.flush()

        xp = award_cycle_question_xp(
            db_session, cycle_student.id, "q_streak_7", 1, user_role="student",
        )
        # base 100 * 1.25 = 125
        assert xp == 125
        db_session.commit()

    def test_question_streak_multiplier_multi_day_14(self, db_session, cycle_student):
        """14-day streak multiplier (1.5) applies (multi-day streak)."""
        from app.models.xp import XpSummary
        from app.services.xp_service import award_cycle_question_xp

        summary = XpSummary(student_id=cycle_student.id, current_streak=14)
        db_session.add(summary)
        db_session.flush()

        xp = award_cycle_question_xp(
            db_session, cycle_student.id, "q_streak_14", 2, user_role="student",
        )
        # base 70 * 1.5 = 105
        assert xp == 105
        db_session.commit()

    def test_chunk_bonus_streak_multiplier_applied(self, db_session, cycle_student):
        """Streak multiplier also applies to chunk bonus."""
        from app.models.xp import XpSummary
        from app.services.xp_service import award_cycle_chunk_bonus

        summary = XpSummary(student_id=cycle_student.id, current_streak=30)
        db_session.add(summary)
        db_session.flush()

        xp = award_cycle_chunk_bonus(
            db_session, cycle_student.id, "chunk_streak_30", user_role="student",
        )
        # base 50 * 1.75 = 87
        assert xp == 87
        db_session.commit()


# ── Students-only gate (#4081) ──

class TestStudentsOnlyGate:
    """award_cycle_question_xp + award_cycle_chunk_bonus return 0 for non-students.

    The gate is enforced INSIDE the function, so every caller is safe by default.
    """

    def test_teacher_role_awards_zero_question(self, db_session, cycle_student):
        """user_role='teacher' → returns 0, no ledger row written."""
        from app.models.xp import XpLedger
        from app.services.xp_service import award_cycle_question_xp

        xp = award_cycle_question_xp(
            db_session, cycle_student.id, "q_teacher", 1, user_role="teacher",
        )
        assert xp == 0
        db_session.commit()

        entry = (
            db_session.query(XpLedger)
            .filter(
                XpLedger.student_id == cycle_student.id,
                XpLedger.context_id == "cycle_question_q_teacher",
            )
            .first()
        )
        assert entry is None, "No ledger row should be written for teacher role"

    def test_parent_role_awards_zero_question(self, db_session, cycle_student):
        """user_role='parent' → returns 0."""
        from app.services.xp_service import award_cycle_question_xp

        xp = award_cycle_question_xp(
            db_session, cycle_student.id, "q_parent", 1, user_role="parent",
        )
        assert xp == 0
        db_session.commit()

    def test_missing_role_awards_zero_question(self, db_session, cycle_student):
        """Missing/empty role → returns 0."""
        from app.services.xp_service import award_cycle_question_xp

        assert award_cycle_question_xp(
            db_session, cycle_student.id, "q_empty", 1, user_role="",
        ) == 0
        assert award_cycle_question_xp(
            db_session, cycle_student.id, "q_none", 1, user_role=None,
        ) == 0
        db_session.commit()

    def test_teacher_role_awards_zero_chunk(self, db_session, cycle_student):
        """user_role='teacher' → chunk bonus returns 0, no ledger row written."""
        from app.models.xp import XpLedger
        from app.services.xp_service import award_cycle_chunk_bonus

        xp = award_cycle_chunk_bonus(
            db_session, cycle_student.id, "chunk_teacher", user_role="teacher",
        )
        assert xp == 0
        db_session.commit()

        entry = (
            db_session.query(XpLedger)
            .filter(
                XpLedger.student_id == cycle_student.id,
                XpLedger.context_id == "cycle_chunk_bonus_chunk_teacher",
            )
            .first()
        )
        assert entry is None, "No ledger row should be written for teacher role"

    def test_parent_role_awards_zero_chunk(self, db_session, cycle_student):
        """user_role='parent' → chunk bonus returns 0."""
        from app.services.xp_service import award_cycle_chunk_bonus

        xp = award_cycle_chunk_bonus(
            db_session, cycle_student.id, "chunk_parent", user_role="parent",
        )
        assert xp == 0
        db_session.commit()

    def test_missing_role_awards_zero_chunk(self, db_session, cycle_student):
        """Missing/empty role → chunk bonus returns 0."""
        from app.services.xp_service import award_cycle_chunk_bonus

        assert award_cycle_chunk_bonus(
            db_session, cycle_student.id, "chunk_empty", user_role="",
        ) == 0
        assert award_cycle_chunk_bonus(
            db_session, cycle_student.id, "chunk_none", user_role=None,
        ) == 0
        db_session.commit()


# ── attempt_number coercion (#4087 S-3) ──


class TestAttemptNumberCoercion:
    """``attempt_number`` should coerce via ``int()`` so callers passing
    strings or floats still receive XP instead of silently getting 0.
    """

    def test_string_attempt_number_accepted(self, db_session, cycle_student):
        """String '1' coerces to int(1) → full 100 XP."""
        from app.services.xp_service import award_cycle_question_xp
        xp = award_cycle_question_xp(
            db_session, cycle_student.id, "q_str", "1", user_role="student",
        )
        assert xp == 100
        db_session.commit()

    def test_float_attempt_number_accepted(self, db_session, cycle_student):
        """Float 1.0 coerces to int(1) → full 100 XP."""
        from app.services.xp_service import award_cycle_question_xp
        xp = award_cycle_question_xp(
            db_session, cycle_student.id, "q_float", 1.0, user_role="student",
        )
        assert xp == 100
        db_session.commit()

    def test_invalid_attempt_number_logs_and_zero(
        self, db_session, cycle_student, caplog,
    ):
        """Un-coercible values log a warning and return 0."""
        import logging

        from app.services.xp_service import award_cycle_question_xp

        with caplog.at_level(logging.WARNING, logger="app.services.xp_service"):
            xp = award_cycle_question_xp(
                db_session, cycle_student.id, "q_bad", "abc", user_role="student",
            )
        assert xp == 0
        assert any(
            "Invalid attempt_number" in rec.message for rec in caplog.records
        )
        db_session.commit()


# ── Action-type registration ──

class TestActionTypesRegistered:
    def test_cycle_action_types_present(self):
        """Both cycle action types are registered in XP_ACTIONS."""
        from app.services.xp_service import XP_ACTIONS
        assert "cycle_question_correct" in XP_ACTIONS
        assert "cycle_chunk_bonus" in XP_ACTIONS

    def test_daily_caps_tuned_for_two_sessions(self):
        """Daily caps reflect ~2 sessions/day target (#4081)."""
        from app.services.xp_service import XP_ACTIONS
        # 2 sessions × 3 correct attempts × 100 = 600
        assert XP_ACTIONS["cycle_question_correct"]["daily_cap"] == 600
        # ~6 chunks × 50 = 300
        assert XP_ACTIONS["cycle_chunk_bonus"]["daily_cap"] == 300

    def test_attempt_map_values(self):
        """Verify the documented diminishing-returns mapping."""
        from app.services.xp_service import CYCLE_QUESTION_XP_BY_ATTEMPT
        assert CYCLE_QUESTION_XP_BY_ATTEMPT[1] == 100
        assert CYCLE_QUESTION_XP_BY_ATTEMPT[2] == 70
        assert CYCLE_QUESTION_XP_BY_ATTEMPT.get(3) == 40
        assert CYCLE_QUESTION_XP_BY_ATTEMPT.get(4, 0) == 0
