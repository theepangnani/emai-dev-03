"""Tests for CB-DCI-001 M0-2 data model (#4140).

Covers:
  - All 6 tables exist after create_all + _migrate_dci_tables()
  - Column presence on each table
  - Basic CRUD round-trip with defaults
  - Foreign-key cascades (kid -> daily_checkins -> classification_events)
  - Pydantic schema round-trip via from_attributes
  - Migration idempotency (calling _migrate_dci_tables twice is safe)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import inspect as sa_inspect


# ─────────────────────── helpers ───────────────────────

def _make_user(db, email):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email=email,
        full_name=email.split("@")[0],
        role=UserRole("parent"),
        hashed_password=get_password_hash("Password123!"),
    )
    db.add(user)
    db.flush()
    return user


def _make_student(db, parent_user_id, email_suffix):
    from app.core.security import get_password_hash
    from app.models.student import Student
    from app.models.user import User, UserRole

    kid_user = User(
        email=f"kid_{email_suffix}@test.com",
        full_name=f"Kid {email_suffix}",
        role=UserRole("student"),
        hashed_password=get_password_hash("Password123!"),
    )
    db.add(kid_user)
    db.flush()
    s = Student(user_id=kid_user.id, grade_level=5)
    db.add(s)
    db.flush()
    return s


def _make_checkin(db, kid_id, parent_id, **overrides):
    from app.models.dci import DailyCheckin

    payload = dict(
        kid_id=kid_id,
        parent_id=parent_id,
        photo_uris=[],
        text_content="hello world",
    )
    payload.update(overrides)
    c = DailyCheckin(**payload)
    db.add(c)
    db.flush()
    return c


# ─────────────────────── schema presence ───────────────────────

class TestDCISchema:
    EXPECTED_TABLES = {
        "daily_checkins",
        "classification_events",
        "ai_summaries",
        "conversation_starters",
        "checkin_streak_summary",
        "checkin_consent",
    }

    def test_all_six_tables_exist(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        names = set(inspector.get_table_names())
        for t in self.EXPECTED_TABLES:
            assert t in names, f"table {t} should exist after create_all/_migrate_dci_tables"

    def test_daily_checkins_columns(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("daily_checkins")}
        assert cols >= {
            "id",
            "kid_id",
            "parent_id",
            "submitted_at",
            "photo_uris",
            "voice_uri",
            "text_content",
            "source",
        }

    def test_classification_events_columns(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("classification_events")}
        assert cols >= {
            "id",
            "checkin_id",
            "artifact_type",
            "subject",
            "topic",
            "strand_code",
            "deadline_iso",
            "confidence",
            "corrected_by_kid",
            "model_version",
            "created_at",
        }

    def test_ai_summaries_columns(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("ai_summaries")}
        assert cols >= {
            "id",
            "kid_id",
            "summary_date",
            "summary_json",
            "generated_at",
            "model_version",
            "prompt_hash",
            "policy_blocked",
            "parent_edited",
        }

    def test_conversation_starters_columns(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("conversation_starters")}
        assert cols >= {
            "id",
            "summary_id",
            "text",
            "was_used",
            "parent_feedback",
            "regenerated_from",
            "created_at",
        }

    def test_checkin_streak_summary_columns(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("checkin_streak_summary")}
        assert cols >= {
            "kid_id",
            "current_streak",
            "longest_streak",
            "last_checkin_date",
            "updated_at",
        }

    def test_checkin_consent_columns(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("checkin_consent")}
        assert cols >= {
            "parent_id",
            "kid_id",
            "photo_ok",
            "voice_ok",
            "ai_ok",
            "retention_days",
            "updated_at",
        }

    def test_daily_checkins_index_present(self, db_session):
        from app.db.database import engine

        inspector = sa_inspect(engine)
        indexes = {i["name"] for i in inspector.get_indexes("daily_checkins")}
        assert "ix_daily_checkins_kid_date" in indexes


# ─────────────────────── model CRUD ───────────────────────

class TestDCICrud:
    def test_create_daily_checkin_defaults(self, db_session):
        parent = _make_user(db_session, "dci_p1@test.com")
        kid = _make_student(db_session, parent.id, "dci1")
        c = _make_checkin(db_session, kid.id, parent.id)
        db_session.commit()
        db_session.refresh(c)

        assert c.id is not None
        assert c.source == "kid_web"
        assert c.photo_uris == []
        assert c.voice_uri is None
        assert c.text_content == "hello world"
        assert c.submitted_at is not None

    def test_classification_event_with_checkin(self, db_session):
        from app.models.dci import ClassificationEvent

        parent = _make_user(db_session, "dci_p2@test.com")
        kid = _make_student(db_session, parent.id, "dci2")
        c = _make_checkin(db_session, kid.id, parent.id)

        ce = ClassificationEvent(
            checkin_id=c.id,
            artifact_type="text",
            subject="Math",
            topic="Fractions",
            strand_code="B1.1",
            confidence=0.93,
            model_version="gpt-4o-mini-2025",
        )
        db_session.add(ce)
        db_session.commit()
        db_session.refresh(c)

        assert len(c.classifications) == 1
        assert c.classifications[0].subject == "Math"
        assert c.classifications[0].corrected_by_kid is False

    def test_ai_summary_unique_per_kid_date(self, db_session):
        from app.models.dci import AISummary

        parent = _make_user(db_session, "dci_p3@test.com")
        kid = _make_student(db_session, parent.id, "dci3")

        today = date.today()
        s1 = AISummary(
            kid_id=kid.id,
            summary_date=today,
            summary_json={"bullets": ["a", "b"]},
            model_version="claude-sonnet-4.6",
            prompt_hash="abc123",
        )
        db_session.add(s1)
        db_session.commit()

        # Second summary for SAME kid+date should fail uniqueness
        s2 = AISummary(
            kid_id=kid.id,
            summary_date=today,
            summary_json={"bullets": ["c"]},
            model_version="claude-sonnet-4.6",
            prompt_hash="xyz789",
        )
        db_session.add(s2)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_conversation_starter_self_reference(self, db_session):
        from app.models.dci import AISummary, ConversationStarter

        parent = _make_user(db_session, "dci_p4@test.com")
        kid = _make_student(db_session, parent.id, "dci4")

        summary = AISummary(
            kid_id=kid.id,
            summary_date=date.today(),
            summary_json={"bullets": ["x"]},
            model_version="claude-sonnet-4.6",
            prompt_hash="hashv1",
        )
        db_session.add(summary)
        db_session.flush()

        starter1 = ConversationStarter(
            summary_id=summary.id,
            text="What was the most surprising thing today?",
        )
        db_session.add(starter1)
        db_session.flush()

        starter2 = ConversationStarter(
            summary_id=summary.id,
            text="Tell me about the fractions worksheet.",
            regenerated_from=starter1.id,
            parent_feedback="regenerate",
        )
        db_session.add(starter2)
        db_session.commit()
        db_session.refresh(starter2)

        assert starter2.regenerated_from == starter1.id
        assert starter2.parent_feedback == "regenerate"
        assert starter2.was_used is None  # nullable tri-state

    def test_checkin_streak_summary_defaults(self, db_session):
        from app.models.dci import CheckinStreakSummary

        parent = _make_user(db_session, "dci_p5@test.com")
        kid = _make_student(db_session, parent.id, "dci5")

        ss = CheckinStreakSummary(kid_id=kid.id)
        db_session.add(ss)
        db_session.commit()
        db_session.refresh(ss)

        assert ss.current_streak == 0
        assert ss.longest_streak == 0
        assert ss.last_checkin_date is None
        assert ss.updated_at is not None

    def test_checkin_consent_composite_pk_defaults(self, db_session):
        from app.models.dci import CheckinConsent

        parent = _make_user(db_session, "dci_p6@test.com")
        kid = _make_student(db_session, parent.id, "dci6")

        cc = CheckinConsent(parent_id=parent.id, kid_id=kid.id)
        db_session.add(cc)
        db_session.commit()
        db_session.refresh(cc)

        assert cc.photo_ok is False
        assert cc.voice_ok is False
        assert cc.ai_ok is False
        assert cc.retention_days == 90
        assert cc.updated_at is not None

    def test_checkin_consent_composite_pk_uniqueness(self, db_session):
        from app.models.dci import CheckinConsent

        parent = _make_user(db_session, "dci_p7@test.com")
        kid = _make_student(db_session, parent.id, "dci7")

        cc1 = CheckinConsent(parent_id=parent.id, kid_id=kid.id, photo_ok=True)
        db_session.add(cc1)
        db_session.commit()

        # #4250 — expunge the persistent instance from the identity map
        # before staging the duplicate so SQLAlchemy doesn't emit a
        # "New instance conflicts with persistent instance" SAWarning
        # when we add a second row with the same composite PK.
        db_session.expunge(cc1)

        # Same parent+kid pair must fail
        cc2 = CheckinConsent(parent_id=parent.id, kid_id=kid.id, voice_ok=True)
        db_session.add(cc2)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()


# ─────────────────────── cascades ───────────────────────

class TestDCICascades:
    def test_delete_checkin_cascades_classifications(self, db_session):
        from app.models.dci import ClassificationEvent

        parent = _make_user(db_session, "dci_casc1@test.com")
        kid = _make_student(db_session, parent.id, "dcicasc1")
        c = _make_checkin(db_session, kid.id, parent.id)
        ce = ClassificationEvent(
            checkin_id=c.id, artifact_type="photo"
        )
        db_session.add(ce)
        db_session.commit()
        ce_id = ce.id

        db_session.delete(c)
        db_session.commit()

        assert (
            db_session.query(ClassificationEvent)
            .filter(ClassificationEvent.id == ce_id)
            .first()
            is None
        )

    def test_delete_summary_cascades_starters(self, db_session):
        from app.models.dci import AISummary, ConversationStarter

        parent = _make_user(db_session, "dci_casc2@test.com")
        kid = _make_student(db_session, parent.id, "dcicasc2")
        summary = AISummary(
            kid_id=kid.id,
            summary_date=date.today(),
            summary_json={"bullets": []},
            model_version="m",
            prompt_hash="h",
        )
        db_session.add(summary)
        db_session.flush()
        st = ConversationStarter(summary_id=summary.id, text="?")
        db_session.add(st)
        db_session.commit()
        st_id = st.id

        db_session.delete(summary)
        db_session.commit()

        assert (
            db_session.query(ConversationStarter)
            .filter(ConversationStarter.id == st_id)
            .first()
            is None
        )


# ─────────────────────── Pydantic schemas ───────────────────────

class TestDCISchemas:
    def test_daily_checkin_response_from_orm(self, db_session):
        from app.schemas.dci import DailyCheckinResponse

        parent = _make_user(db_session, "dci_s1@test.com")
        kid = _make_student(db_session, parent.id, "dcis1")
        c = _make_checkin(
            db_session, kid.id, parent.id,
            photo_uris=["gs://b/o/1.jpg"],
            voice_uri="gs://b/o/v.opus",
            text_content="today was great",
            source="kid_mobile",
        )
        db_session.commit()
        db_session.refresh(c)

        resp = DailyCheckinResponse.model_validate(c)
        assert resp.id == c.id
        assert resp.kid_id == kid.id
        assert resp.parent_id == parent.id
        assert resp.photo_uris == ["gs://b/o/1.jpg"]
        assert resp.voice_uri == "gs://b/o/v.opus"
        assert resp.text_content == "today was great"
        assert resp.source == "kid_mobile"
        assert isinstance(resp.submitted_at, datetime)

    def test_daily_checkin_create_validation(self):
        from app.schemas.dci import DailyCheckinCreate

        # source pattern enforced
        with pytest.raises(Exception):
            DailyCheckinCreate(kid_id=1, parent_id=2, source="kid_carrier_pigeon")

        # text_content max length 280
        with pytest.raises(Exception):
            DailyCheckinCreate(
                kid_id=1, parent_id=2, text_content="x" * 281
            )

        # voice_uri max length 500
        with pytest.raises(Exception):
            DailyCheckinCreate(
                kid_id=1, parent_id=2, voice_uri="x" * 501
            )

    def test_classification_event_create_artifact_type_pattern(self):
        from app.schemas.dci import ClassificationEventCreate

        # Valid ones
        for t in ("photo", "voice", "text"):
            ClassificationEventCreate(checkin_id=1, artifact_type=t)

        with pytest.raises(Exception):
            ClassificationEventCreate(checkin_id=1, artifact_type="video")

    def test_classification_event_confidence_bounded(self):
        from app.schemas.dci import ClassificationEventCreate

        ClassificationEventCreate(checkin_id=1, artifact_type="text", confidence=0.0)
        ClassificationEventCreate(checkin_id=1, artifact_type="text", confidence=1.0)

        with pytest.raises(Exception):
            ClassificationEventCreate(
                checkin_id=1, artifact_type="text", confidence=1.5
            )

    def test_ai_summary_response_from_orm(self, db_session):
        from app.models.dci import AISummary
        from app.schemas.dci import AISummaryResponse

        parent = _make_user(db_session, "dci_s2@test.com")
        kid = _make_student(db_session, parent.id, "dcis2")
        s = AISummary(
            kid_id=kid.id,
            summary_date=date.today(),
            summary_json={"bullets": ["a"], "tone": "warm"},
            model_version="claude-sonnet-4.6",
            prompt_hash="abc",
        )
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)

        resp = AISummaryResponse.model_validate(s)
        assert resp.summary_json == {"bullets": ["a"], "tone": "warm"}
        assert resp.policy_blocked is False
        assert resp.parent_edited is False

    def test_conversation_starter_feedback_pattern(self):
        from app.schemas.dci import ConversationStarterFeedback

        ConversationStarterFeedback(was_used=True, parent_feedback="thumbs_up")
        ConversationStarterFeedback(parent_feedback="regenerate")
        ConversationStarterFeedback(was_used=False)
        # #4225 — explicit untoggle signal from the frontend; route
        # handler interprets it as `was_used = false`.
        ConversationStarterFeedback(parent_feedback="undo_used")

        with pytest.raises(Exception):
            ConversationStarterFeedback(parent_feedback="not_a_value")

    def test_undo_used_is_schema_only_not_model_enum(self):
        """#4225 — `undo_used` is a transient signal interpreted by the
        route handler as ``was_used = false``; it must NOT appear in the
        DB-level ``PARENT_FEEDBACK_VALUES`` tuple / CHECK constraint.
        Pinning here so a future "tidy" doesn't silently start
        persisting it."""
        from app.models.dci import PARENT_FEEDBACK_VALUES

        assert "undo_used" not in PARENT_FEEDBACK_VALUES
        assert PARENT_FEEDBACK_VALUES == ("thumbs_up", "regenerate")

    def test_checkin_consent_retention_days_bounds(self):
        from app.schemas.dci import CheckinConsentCreate

        CheckinConsentCreate(parent_id=1, kid_id=2, retention_days=1)
        CheckinConsentCreate(parent_id=1, kid_id=2, retention_days=1095)

        with pytest.raises(Exception):
            CheckinConsentCreate(parent_id=1, kid_id=2, retention_days=0)
        with pytest.raises(Exception):
            CheckinConsentCreate(parent_id=1, kid_id=2, retention_days=2000)


# ─────────────────────── CHECK constraint enforcement ───────────────────────

class TestDCICheckConstraints:
    """Verify DB-level CheckConstraints reject invalid enum values even when
    Pydantic validation is bypassed (raw ORM writes, future migrations, etc).
    """

    def test_daily_checkins_source_check_rejects_invalid(self, db_session):
        from app.models.dci import DailyCheckin

        parent = _make_user(db_session, "dci_ck1@test.com")
        kid = _make_student(db_session, parent.id, "dcick1")

        bad = DailyCheckin(
            kid_id=kid.id,
            parent_id=parent.id,
            photo_uris=[],
            source="kid_carrier_pigeon",  # not in CHECKIN_SOURCES
        )
        db_session.add(bad)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_classification_events_artifact_type_check_rejects_invalid(self, db_session):
        from app.models.dci import ClassificationEvent

        parent = _make_user(db_session, "dci_ck2@test.com")
        kid = _make_student(db_session, parent.id, "dcick2")
        c = _make_checkin(db_session, kid.id, parent.id)

        bad = ClassificationEvent(
            checkin_id=c.id,
            artifact_type="video",  # not in ARTIFACT_TYPES
        )
        db_session.add(bad)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_conversation_starters_parent_feedback_check_rejects_invalid(self, db_session):
        from app.models.dci import AISummary, ConversationStarter

        parent = _make_user(db_session, "dci_ck3@test.com")
        kid = _make_student(db_session, parent.id, "dcick3")
        summary = AISummary(
            kid_id=kid.id,
            summary_date=date.today(),
            summary_json={"bullets": []},
            model_version="m",
            prompt_hash="h",
        )
        db_session.add(summary)
        db_session.flush()

        bad = ConversationStarter(
            summary_id=summary.id,
            text="?",
            parent_feedback="not_a_value",  # not in PARENT_FEEDBACK_VALUES
        )
        db_session.add(bad)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_conversation_starters_parent_feedback_allows_null(self, db_session):
        """parent_feedback is nullable; CHECK must permit NULL."""
        from app.models.dci import AISummary, ConversationStarter

        parent = _make_user(db_session, "dci_ck4@test.com")
        kid = _make_student(db_session, parent.id, "dcick4")
        summary = AISummary(
            kid_id=kid.id,
            summary_date=date.today(),
            summary_json={"bullets": []},
            model_version="m",
            prompt_hash="h",
        )
        db_session.add(summary)
        db_session.flush()

        ok = ConversationStarter(summary_id=summary.id, text="?")
        db_session.add(ok)
        db_session.commit()
        db_session.refresh(ok)
        assert ok.parent_feedback is None


# ─────────────────────── migration idempotency ───────────────────────

class TestDCIMigrationIdempotency:
    def test_calling_migrate_twice_is_safe(self, db_session):
        """Re-running _migrate_dci_tables() must not raise — every CREATE
        TABLE / CREATE INDEX uses IF NOT EXISTS, and the function catches
        per-statement failures.

        NOTE: This test reaches into ``main._migrate_dci_tables`` — the single
        startup entry point for DCI DDL. If the function is renamed or
        relocated (e.g. to ``app/db/migrations.py``), this test must move
        with it.
        """
        import main as main_module

        # Should not raise on second invocation
        main_module._migrate_dci_tables()
        main_module._migrate_dci_tables()

        # Tables still present and queryable
        from sqlalchemy import inspect as _inspect

        from app.db.database import engine

        inspector = _inspect(engine)
        names = set(inspector.get_table_names())
        for t in TestDCISchema.EXPECTED_TABLES:
            assert t in names

    def test_streak_update_round_trip(self, db_session):
        from app.models.dci import CheckinStreakSummary

        parent = _make_user(db_session, "dci_idem1@test.com")
        kid = _make_student(db_session, parent.id, "dciidem1")

        ss = CheckinStreakSummary(
            kid_id=kid.id,
            current_streak=3,
            longest_streak=5,
            last_checkin_date=date.today() - timedelta(days=1),
        )
        db_session.add(ss)
        db_session.commit()
        db_session.refresh(ss)

        assert ss.current_streak == 3
        assert ss.longest_streak == 5
        assert ss.last_checkin_date == date.today() - timedelta(days=1)
