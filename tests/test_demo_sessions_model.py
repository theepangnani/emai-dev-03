"""Tests for the demo_sessions table/model (CB-DEMO-001, #3600)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect as sa_inspect


def _email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


class TestDemoSessionsTable:
    def test_table_exists(self, db_session):
        """demo_sessions table should exist after startup migration."""
        from app.db.database import engine

        inspector = sa_inspect(engine)
        assert "demo_sessions" in inspector.get_table_names()

    def test_expected_columns_present(self, db_session):
        """All PRD §11.5 columns should be present on demo_sessions."""
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("demo_sessions")}
        expected = {
            "id",
            "created_at",
            "email_hash",
            "email",
            "full_name",
            "role",
            "consent_ts",
            "verified",
            "verified_ts",
            "verification_token_hash",
            "verification_expires_at",
            "fallback_code_hash",
            "fallback_code_expires_at",
            "generations_count",
            "generations_json",
            "moat_engagement_json",
            "source_ip_hash",
            "user_agent",
            "admin_status",
            "archived_at",
        }
        missing = expected - cols
        assert not missing, f"Missing columns: {missing}"

    def test_email_hash_index_exists(self, db_session):
        """Index idx_demo_sessions_email_hash should exist."""
        from app.db.database import engine

        inspector = sa_inspect(engine)
        index_names = {ix["name"] for ix in inspector.get_indexes("demo_sessions")}
        assert "idx_demo_sessions_email_hash" in index_names


class TestDemoSessionModel:
    def test_create_row(self, db_session):
        """Can create a DemoSession row with required fields and sensible defaults."""
        from app.models.demo_session import DemoSession

        email = "Test.User@Example.com"
        session = DemoSession(
            email_hash=_email_hash(email),
            email=email,
            full_name="Test User",
            role="parent",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.id is not None
        assert session.created_at is not None
        assert session.verified is False
        assert session.generations_count == 0
        assert session.admin_status == "pending"
        assert session.archived_at is None

    def test_json_column_roundtrip(self, db_session):
        """generations_json and moat_engagement_json survive a round-trip."""
        from app.models.demo_session import DemoSession

        email = "json_rt@example.com"
        gens = [
            {
                "ts": "2026-04-18T12:00:00Z",
                "kind": "quiz",
                "subject": "math",
                "prompt_excerpt": "solve 2+2",
            }
        ]
        moat = {"scroll_depth": 0.9, "dwell_ms": 42000}
        session = DemoSession(
            email_hash=_email_hash(email),
            email=email,
            role="student",
            generations_json=gens,
            moat_engagement_json=moat,
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        assert session.generations_json == gens
        assert session.moat_engagement_json == moat

    def test_admin_status_transitions(self, db_session):
        """admin_status can transition pending -> approved/rejected/blocklisted."""
        from app.models.demo_session import DemoSession

        email = "admin_status@example.com"
        session = DemoSession(
            email_hash=_email_hash(email),
            email=email,
            role="teacher",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        assert session.admin_status == "pending"

        for status in ("approved", "rejected", "blocklisted", "pending"):
            session.admin_status = status
            db_session.commit()
            db_session.refresh(session)
            assert session.admin_status == status

    def test_multiple_rows_same_email_hash_allowed(self, db_session):
        """No unique constraint on (email_hash, created_at) — two rows can share email_hash."""
        from app.models.demo_session import DemoSession

        email = "dup@example.com"
        eh = _email_hash(email)

        s1 = DemoSession(email_hash=eh, email=email, role="parent")
        s2 = DemoSession(email_hash=eh, email=email, role="parent")
        db_session.add_all([s1, s2])
        db_session.commit()
        db_session.refresh(s1)
        db_session.refresh(s2)

        assert s1.id != s2.id
        rows = [
            r for r in db_session.query(DemoSession).filter_by(email_hash=eh).all()
        ]
        assert len(rows) >= 2

    def test_verified_flow(self, db_session):
        """Setting verified=True plus verified_ts reflects a verified session."""
        from app.models.demo_session import DemoSession

        email = "verified@example.com"
        session = DemoSession(
            email_hash=_email_hash(email),
            email=email,
            role="other",
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        session.verified = True
        session.verified_ts = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(session)

        assert session.verified is True
        assert session.verified_ts is not None

    def test_role_check_constraint_rejects_invalid(self, db_session):
        """role must be one of parent|student|teacher|other."""
        from app.models.demo_session import DemoSession

        email = "badrole@example.com"
        session = DemoSession(
            email_hash=_email_hash(email),
            email=email,
            role="admin",  # invalid
        )
        db_session.add(session)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_admin_status_check_constraint_rejects_invalid(self, db_session):
        """admin_status must be one of pending|approved|rejected|blocklisted (#3623)."""
        from app.models.demo_session import DemoSession

        email = "badadminstatus@example.com"
        session = DemoSession(
            email_hash=_email_hash(email),
            email=email,
            role="parent",
            admin_status="nonsense",  # invalid
        )
        db_session.add(session)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()
