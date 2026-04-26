"""Tests for the DCI Check-in Streak service (CB-DCI-001 M0-8, #4145).

Covers:
- Idempotent re-record on the same day
- First-ever check-in starts streak at 1
- Multi-day school-day streak increments
- Weekend gap preserves streak (no break)
- Holiday gap preserves streak (no break)
- Real missed school day breaks the streak (silently)
- Recovery after a break starts a new streak at 1
- Never-guilt: ``get_streak`` payload exposes only current/longest/last/days
- Existing study-streak path still passes (regression smoke)
"""
from __future__ import annotations

import secrets
from datetime import date, timedelta

import pytest

from conftest import PASSWORD, _auth


def _hex():
    return secrets.token_hex(4)


# ── Fixtures ────────────────────────────────────────────────────────


# Track every User+Student pair created by ``kid_record`` / ``linked_family``
# in the current test so the autouse cleanup fixture can wipe them at teardown
# (#4181 — keep the session-scoped DB from growing unboundedly across the
# full smoke run).
_CREATED_USERS: list[int] = []
_CREATED_STUDENTS: list[int] = []


@pytest.fixture(autouse=True)
def cleanup_test_kids(db_session):
    """Autouse teardown: delete every User+Student row (and its dependent
    CheckinStreakSummary / StreakLog / parent_students rows) created by the
    DCI fixtures during this test. Keeps the session-scoped SQLite DB
    bounded across the full smoke run (#4181)."""
    _CREATED_USERS.clear()
    _CREATED_STUDENTS.clear()

    yield

    if not _CREATED_USERS and not _CREATED_STUDENTS:
        return

    from sqlalchemy import delete

    from app.models.dci import CheckinStreakSummary
    from app.models.student import Student, parent_students
    from app.models.user import User
    from app.models.xp import StreakLog, XpSummary

    try:
        if _CREATED_STUDENTS:
            db_session.query(CheckinStreakSummary).filter(
                CheckinStreakSummary.kid_id.in_(_CREATED_STUDENTS)
            ).delete(synchronize_session=False)
            db_session.execute(
                delete(parent_students).where(
                    parent_students.c.student_id.in_(_CREATED_STUDENTS)
                )
            )

        if _CREATED_USERS:
            db_session.query(StreakLog).filter(
                StreakLog.student_id.in_(_CREATED_USERS)
            ).delete(synchronize_session=False)
            db_session.query(XpSummary).filter(
                XpSummary.student_id.in_(_CREATED_USERS)
            ).delete(synchronize_session=False)
            db_session.execute(
                delete(parent_students).where(
                    parent_students.c.parent_id.in_(_CREATED_USERS)
                )
            )

        if _CREATED_STUDENTS:
            db_session.query(Student).filter(
                Student.id.in_(_CREATED_STUDENTS)
            ).delete(synchronize_session=False)
        if _CREATED_USERS:
            db_session.query(User).filter(
                User.id.in_(_CREATED_USERS)
            ).delete(synchronize_session=False)

        db_session.commit()
    except Exception:
        db_session.rollback()
    finally:
        _CREATED_USERS.clear()
        _CREATED_STUDENTS.clear()


@pytest.fixture()
def kid_record(db_session):
    """Create a fresh User+Student row pair per test (no cross-test bleed)."""
    from app.core.security import get_password_hash
    from app.models.student import Student
    from app.models.user import User, UserRole

    tag = _hex()
    hashed = get_password_hash(PASSWORD)

    kid_user = User(
        email=f"dci_kid_{tag}@test.com",
        full_name=f"DCI Kid {tag}",
        username=f"dci_kid_{tag}",
        role=UserRole.STUDENT,
        roles="student",
        hashed_password=hashed,
        onboarding_completed=True,
        email_verified=True,
    )
    db_session.add(kid_user)
    db_session.flush()

    student = Student(user_id=kid_user.id)
    db_session.add(student)
    db_session.commit()

    _CREATED_USERS.append(kid_user.id)
    _CREATED_STUDENTS.append(student.id)

    yield {"user": kid_user, "student": student}


@pytest.fixture()
def linked_family(db_session):
    """Parent + kid + linkage for the API auth tests."""
    from sqlalchemy import insert

    from app.core.security import get_password_hash
    from app.models.student import RelationshipType, Student, parent_students
    from app.models.user import User, UserRole

    tag = _hex()
    hashed = get_password_hash(PASSWORD)

    parent = User(
        email=f"dci_parent_{tag}@test.com",
        full_name=f"DCI Parent {tag}",
        username=f"dci_parent_{tag}",
        role=UserRole.PARENT,
        roles="parent",
        hashed_password=hashed,
        onboarding_completed=True,
        email_verified=True,
    )
    kid_user = User(
        email=f"dci_familykid_{tag}@test.com",
        full_name=f"DCI Family Kid {tag}",
        username=f"dci_familykid_{tag}",
        role=UserRole.STUDENT,
        roles="student",
        hashed_password=hashed,
        onboarding_completed=True,
        email_verified=True,
    )
    outsider = User(
        email=f"dci_outsider_{tag}@test.com",
        full_name=f"DCI Outsider {tag}",
        username=f"dci_outsider_{tag}",
        role=UserRole.PARENT,
        roles="parent",
        hashed_password=hashed,
        onboarding_completed=True,
        email_verified=True,
    )
    db_session.add_all([parent, kid_user, outsider])
    db_session.flush()

    student = Student(user_id=kid_user.id)
    db_session.add(student)
    db_session.flush()

    db_session.execute(
        insert(parent_students).values(
            parent_id=parent.id,
            student_id=student.id,
            relationship_type=RelationshipType.GUARDIAN,
        )
    )
    db_session.commit()

    _CREATED_USERS.extend([parent.id, kid_user.id, outsider.id])
    _CREATED_STUDENTS.append(student.id)

    return {
        "parent": parent,
        "kid_user": kid_user,
        "student": student,
        "outsider": outsider,
    }


# ── School-day helpers ──────────────────────────────────────────────


def _next_monday(today: date) -> date:
    """Return a Monday on/before today (so day-N-back chains stay weekday)."""
    days_back = (today.weekday()) % 7  # Mon=0
    return today - timedelta(days=days_back)


# ── Service tests ───────────────────────────────────────────────────


class TestRecordCheckin:
    def test_first_checkin_starts_streak(self, db_session, kid_record):
        from app.services.dci_streak_service import record_checkin

        kid = kid_record["student"]
        d = date(2026, 4, 13)  # Monday
        summary = record_checkin(db_session, kid.id, checkin_date=d)

        assert summary.current_streak == 1
        assert summary.longest_streak == 1
        assert summary.last_checkin_date == d

    def test_idempotent_same_day(self, db_session, kid_record):
        from app.models.xp import StreakLog
        from app.services.dci_streak_service import (
            ACTION_TYPE_DAILY_CHECKIN,
            record_checkin,
        )

        kid = kid_record["student"]
        kid_user = kid_record["user"]
        d = date(2026, 4, 13)

        s1 = record_checkin(db_session, kid.id, checkin_date=d)
        s2 = record_checkin(db_session, kid.id, checkin_date=d)

        assert s1.current_streak == 1
        assert s2.current_streak == 1
        assert s1.last_checkin_date == s2.last_checkin_date == d

        # Exactly one StreakLog row for the daily_checkin stream.
        log_count = (
            db_session.query(StreakLog)
            .filter(
                StreakLog.student_id == kid_user.id,
                StreakLog.log_date == d,
                StreakLog.qualifying_action == ACTION_TYPE_DAILY_CHECKIN,
            )
            .count()
        )
        assert log_count == 1

    def test_consecutive_school_days_increment(self, db_session, kid_record):
        from app.services.dci_streak_service import record_checkin

        kid = kid_record["student"]
        # Mon Apr 13 → Tue Apr 14 → Wed Apr 15 (all weekdays in 2026)
        record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 13))
        record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 14))
        s = record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 15))

        assert s.current_streak == 3
        assert s.longest_streak == 3

    def test_weekend_skip_preserves_streak(self, db_session, kid_record):
        """Friday → Monday counts as +1 (Sat/Sun are non-school days)."""
        from app.services.dci_streak_service import record_checkin

        kid = kid_record["student"]
        # Apr 17 2026 = Friday, Apr 20 2026 = Monday
        record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 17))
        s = record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 20))

        assert s.current_streak == 2
        assert s.last_checkin_date == date(2026, 4, 20)

    def test_holiday_skip_preserves_streak(self, db_session, kid_record):
        """A weekday holiday in the gap is treated as a non-school day."""
        from app.models.holiday import HolidayDate
        from app.services.dci_streak_service import record_checkin

        kid = kid_record["student"]
        # Mon Apr 13 → Wed Apr 15, with Tue Apr 14 marked as a PD day.
        pd_day = date(2026, 4, 14)
        existing = (
            db_session.query(HolidayDate)
            .filter(HolidayDate.date == pd_day)
            .first()
        )
        if existing is None:
            db_session.add(HolidayDate(date=pd_day, name="Test PD Day"))
            db_session.commit()

        try:
            record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 13))
            s = record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 15))
            assert s.current_streak == 2
        finally:
            db_session.query(HolidayDate).filter(
                HolidayDate.date == pd_day
            ).delete()
            db_session.commit()

    def test_missed_school_day_breaks_then_recovers(self, db_session, kid_record):
        """Real missed weekday → streak resets to 1 on next check-in."""
        from app.services.dci_streak_service import record_checkin

        kid = kid_record["student"]
        # Mon Apr 13 → skip Tue → skip Wed → Thu Apr 16
        record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 13))
        s = record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 16))

        assert s.current_streak == 1  # broken & restarted
        assert s.longest_streak == 1  # never grew past 1 in this stream

        # Next school day continues from the new base.
        s2 = record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 17))
        assert s2.current_streak == 2

    def test_longest_streak_persists_after_break(self, db_session, kid_record):
        from app.services.dci_streak_service import record_checkin

        kid = kid_record["student"]
        # Build a 3-day streak then break.
        for d in (date(2026, 4, 13), date(2026, 4, 14), date(2026, 4, 15)):
            record_checkin(db_session, kid.id, checkin_date=d)

        # Big gap: skip Apr 16 (Thu) and Apr 17 (Fri).
        s = record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 20))
        assert s.current_streak == 1
        assert s.longest_streak == 3


# ── get_streak: never-guilt payload shape ───────────────────────────


class TestGetStreak:
    def test_payload_shape_no_break_info(self, db_session, kid_record):
        from app.services.dci_streak_service import get_streak, record_checkin

        kid = kid_record["student"]
        record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 13))
        record_checkin(db_session, kid.id, checkin_date=date(2026, 4, 14))

        payload = get_streak(db_session, kid.id)

        assert set(payload.keys()) == {
            "current",
            "longest",
            "last_checkin_date",
            "days_until_next_milestone",
        }
        assert payload["current"] == 2
        assert payload["longest"] == 2
        assert payload["last_checkin_date"] == "2026-04-14"
        assert payload["days_until_next_milestone"] == 1  # next milestone = 3

        # Never-guilt: no break events, no missed-day count, no shame copy.
        forbidden = {
            "broken",
            "broken_at",
            "missed_days",
            "streak_broken_at",
            "last_break",
        }
        assert forbidden.isdisjoint(payload.keys())

    def test_no_summary_returns_zero(self, db_session, kid_record):
        from app.services.dci_streak_service import get_streak

        kid = kid_record["student"]
        payload = get_streak(db_session, kid.id)

        assert payload["current"] == 0
        assert payload["longest"] == 0
        assert payload["last_checkin_date"] is None
        assert payload["days_until_next_milestone"] == 3


# ── Nightly evaluator ───────────────────────────────────────────────


class TestEvaluateCheckinStreak:
    def test_missed_school_day_breaks_silently(self, db_session, kid_record, monkeypatch):
        """If the kid did NOT check in yesterday (and yesterday was a school day),
        the nightly evaluator silently zeros ``current_streak`` without surfacing
        anything to the kid."""
        from app.models.dci import CheckinStreakSummary
        from app.services import dci_streak_service

        kid = kid_record["student"]
        summary = CheckinStreakSummary(
            kid_id=kid.id,
            current_streak=4,
            longest_streak=4,
            last_checkin_date=date.today() - timedelta(days=2),
        )
        db_session.add(summary)
        db_session.commit()

        # Force "yesterday" to be a Wednesday (a guaranteed school day) so
        # the test is deterministic regardless of when it runs.
        fake_today = date(2026, 4, 16)  # Thursday → yesterday = Wed Apr 15
        real_date = dci_streak_service.date

        class _FrozenDate(real_date):
            @classmethod
            def today(cls):
                return fake_today

        monkeypatch.setattr(dci_streak_service, "date", _FrozenDate)

        # Move the summary's last_checkin_date back so it's stale relative to
        # the frozen "yesterday".
        summary.last_checkin_date = fake_today - timedelta(days=3)
        db_session.commit()

        result = dci_streak_service.evaluate_checkin_streak(db_session, kid.id)
        assert result == "broken"

        db_session.refresh(summary)
        assert summary.current_streak == 0
        # ``longest_streak`` is preserved — never-guilt does not erase history.
        assert summary.longest_streak == 4

    def test_weekend_yesterday_skips(self, db_session, kid_record, monkeypatch):
        from app.models.dci import CheckinStreakSummary
        from app.services import dci_streak_service

        kid = kid_record["student"]
        summary = CheckinStreakSummary(
            kid_id=kid.id,
            current_streak=4,
            longest_streak=4,
            last_checkin_date=date(2026, 4, 17),  # Fri
        )
        db_session.add(summary)
        db_session.commit()

        # Frozen "today" = Sun Apr 19 → yesterday = Sat Apr 18 (weekend).
        fake_today = date(2026, 4, 19)
        real_date = dci_streak_service.date

        class _FrozenDate(real_date):
            @classmethod
            def today(cls):
                return fake_today

        monkeypatch.setattr(dci_streak_service, "date", _FrozenDate)

        result = dci_streak_service.evaluate_checkin_streak(db_session, kid.id)
        assert result == "skip"

        db_session.refresh(summary)
        assert summary.current_streak == 4  # untouched

    def test_holiday_yesterday_skips(self, db_session, kid_record, monkeypatch):
        from app.models.dci import CheckinStreakSummary
        from app.models.holiday import HolidayDate
        from app.services import dci_streak_service

        kid = kid_record["student"]
        summary = CheckinStreakSummary(
            kid_id=kid.id,
            current_streak=4,
            longest_streak=4,
            last_checkin_date=date(2026, 4, 13),
        )
        db_session.add(summary)
        db_session.commit()

        # Tue Apr 14 = "yesterday" relative to Wed Apr 15. Make it a PD day.
        pd_day = date(2026, 4, 14)
        if not (
            db_session.query(HolidayDate)
            .filter(HolidayDate.date == pd_day)
            .first()
        ):
            db_session.add(HolidayDate(date=pd_day, name="Test PD Day"))
            db_session.commit()

        try:
            fake_today = date(2026, 4, 15)
            real_date = dci_streak_service.date

            class _FrozenDate(real_date):
                @classmethod
                def today(cls):
                    return fake_today

            monkeypatch.setattr(dci_streak_service, "date", _FrozenDate)

            result = dci_streak_service.evaluate_checkin_streak(db_session, kid.id)
            assert result == "skip"

            db_session.refresh(summary)
            assert summary.current_streak == 4
        finally:
            db_session.query(HolidayDate).filter(
                HolidayDate.date == pd_day
            ).delete()
            db_session.commit()


class TestEvaluateOrphanedSummary:
    """Regression guard for #4177 — when the StreakLog row for yesterday is
    missing but ``summary.last_checkin_date`` happens to equal yesterday,
    the evaluator must still break the streak (StreakLog is the source of
    truth, not the aggregate).
    """

    def test_orphaned_summary_breaks_silently(
        self, db_session, kid_record, monkeypatch
    ):
        from app.models.dci import CheckinStreakSummary
        from app.models.xp import StreakLog
        from app.services import dci_streak_service

        kid = kid_record["student"]
        kid_user = kid_record["user"]

        # Frozen "today" = Wed Apr 15, "yesterday" = Tue Apr 14 (school day).
        fake_today = date(2026, 4, 15)
        real_date = dci_streak_service.date

        class _FrozenDate(real_date):
            @classmethod
            def today(cls):
                return fake_today

        monkeypatch.setattr(dci_streak_service, "date", _FrozenDate)

        # Stale aggregate claiming yesterday was checked in, but NO StreakLog
        # row exists for that day (simulates a manual delete or migration drift).
        summary = CheckinStreakSummary(
            kid_id=kid.id,
            current_streak=5,
            longest_streak=5,
            last_checkin_date=fake_today - timedelta(days=1),  # Tue Apr 14
        )
        db_session.add(summary)
        db_session.commit()

        # Confirm precondition: no StreakLog row for the daily_checkin stream
        # on yesterday.
        log_count = (
            db_session.query(StreakLog)
            .filter(
                StreakLog.student_id == kid_user.id,
                StreakLog.log_date == fake_today - timedelta(days=1),
                StreakLog.qualifying_action == "daily_checkin",
            )
            .count()
        )
        assert log_count == 0

        result = dci_streak_service.evaluate_checkin_streak(db_session, kid.id)
        assert result == "broken"

        db_session.refresh(summary)
        assert summary.current_streak == 0
        assert summary.longest_streak == 5  # never-guilt: history preserved


class TestPreviousSchoolDayBound:
    """Regression guard for #4178 — exhausting the 30-day backfill must
    return a deterministic value (anchor - MAX_BACKFILL_DAYS), not a
    cursor that drifted past the bound onto a non-school day."""

    def test_pathological_holiday_run_returns_deterministic_anchor(
        self, db_session, kid_record
    ):
        from app.models.holiday import HolidayDate
        from app.services.dci_streak_service import (
            MAX_BACKFILL_DAYS,
            _previous_school_day,
        )

        anchor = date(2026, 6, 1)  # Monday
        # Block the entire MAX_BACKFILL_DAYS window with explicit holidays —
        # combined with weekends, this guarantees no school day is found.
        added = []
        for i in range(1, MAX_BACKFILL_DAYS + 5):
            d = anchor - timedelta(days=i)
            existing = (
                db_session.query(HolidayDate)
                .filter(HolidayDate.date == d)
                .first()
            )
            if existing is None:
                db_session.add(HolidayDate(date=d, name=f"Test bound {i}"))
                added.append(d)
        db_session.commit()

        try:
            result = _previous_school_day(db_session, anchor)
            assert result == anchor - timedelta(days=MAX_BACKFILL_DAYS)
        finally:
            for d in added:
                db_session.query(HolidayDate).filter(
                    HolidayDate.date == d
                ).delete()
            db_session.commit()


# ── Regression: study + DCI streams coexist on same day (#4183) ─────


class TestSameDayCoexistence:
    """The widened ``streak_log`` unique constraint
    (``student_id, log_date, qualifying_action``) must allow both a
    study-streak row AND a DCI check-in row for the same kid on the
    same day. Without the widening, the second INSERT raises
    IntegrityError and silently breaks the DCI write path.
    """

    def test_same_day_study_then_checkin(self, db_session, kid_record):
        from app.models.xp import StreakLog
        from app.services.dci_streak_service import (
            ACTION_TYPE_DAILY_CHECKIN,
            record_checkin,
        )
        from app.services.streak_service import StreakService

        kid_user = kid_record["user"]
        student = kid_record["student"]

        # Study action first (writes (user_id, today, 'study_guide'))
        study_log = StreakService.record_qualifying_action(
            db_session, kid_user.id, "study_guide"
        )
        assert study_log is not None

        # Then DCI check-in (writes (user_id, today, 'daily_checkin'))
        # — must NOT raise IntegrityError.
        record_checkin(db_session, student.id, checkin_date=date.today())

        rows = (
            db_session.query(StreakLog)
            .filter(
                StreakLog.student_id == kid_user.id,
                StreakLog.log_date == date.today(),
            )
            .all()
        )
        actions = sorted(r.qualifying_action for r in rows)
        assert "study_guide" in actions
        assert ACTION_TYPE_DAILY_CHECKIN in actions

    def test_record_checkin_backfills_streak_value(
        self, db_session, kid_record
    ):
        """Regression for #4184 — the inserted StreakLog row must end up
        with streak_value populated without a second SELECT."""
        from app.models.xp import StreakLog
        from app.services.dci_streak_service import (
            ACTION_TYPE_DAILY_CHECKIN,
            record_checkin,
        )

        kid_user = kid_record["user"]
        student = kid_record["student"]

        record_checkin(db_session, student.id, checkin_date=date(2026, 4, 13))
        record_checkin(db_session, student.id, checkin_date=date(2026, 4, 14))

        log = (
            db_session.query(StreakLog)
            .filter(
                StreakLog.student_id == kid_user.id,
                StreakLog.log_date == date(2026, 4, 14),
                StreakLog.qualifying_action == ACTION_TYPE_DAILY_CHECKIN,
            )
            .first()
        )
        assert log is not None
        assert log.streak_value == 2


# ── Regression: existing study streak still works after refactor ────


class TestStudyStreakRegression:
    """The CB-DCI-001 M0-8 refactor must not change study-streak behavior.

    This is a smoke test against the same code path the existing
    ``check_all_streaks`` job uses.
    """

    def test_study_streak_record_and_evaluate(self, db_session, kid_record):
        from app.models.xp import XpSummary
        from app.services.streak_service import StreakService

        kid_user = kid_record["user"]
        # Study-streak path uses ``users.id`` (NOT students.id).
        log = StreakService.record_qualifying_action(
            db_session, kid_user.id, "study_guide"
        )
        assert log.qualifying_action == "study_guide"
        assert log.streak_value == 1

        summary = (
            db_session.query(XpSummary)
            .filter(XpSummary.student_id == kid_user.id)
            .first()
        )
        assert summary.current_streak == 1
        assert summary.longest_streak == 1


# ── API endpoint tests ──────────────────────────────────────────────


class TestStreakAPI:
    def test_kid_can_read_own_streak(self, client, db_session, linked_family):
        from app.services.dci_streak_service import record_checkin

        student = linked_family["student"]
        kid_user = linked_family["kid_user"]
        record_checkin(db_session, student.id, checkin_date=date(2026, 4, 13))

        headers = _auth(client, kid_user.email)
        resp = client.get(f"/api/dci/streak/{student.id}", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["current"] == 1
        assert data["longest"] == 1
        assert data["last_checkin_date"] == "2026-04-13"

    def test_linked_parent_can_read(self, client, db_session, linked_family):
        from app.services.dci_streak_service import record_checkin

        student = linked_family["student"]
        parent = linked_family["parent"]
        record_checkin(db_session, student.id, checkin_date=date(2026, 4, 13))

        headers = _auth(client, parent.email)
        resp = client.get(f"/api/dci/streak/{student.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["current"] == 1

    def test_outsider_parent_blocked(self, client, db_session, linked_family):
        student = linked_family["student"]
        outsider = linked_family["outsider"]

        headers = _auth(client, outsider.email)
        resp = client.get(f"/api/dci/streak/{student.id}", headers=headers)
        assert resp.status_code == 403
