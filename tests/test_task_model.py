"""Tests for CB-TASKSYNC-001 I1 (#3912, #3913) — Task source-attribution columns.

Verifies that the 6 source-* columns and 2 new indexes (one partial unique) are
present after startup migrations run, and that running the migration block a
second time is a no-op (idempotent).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect as sa_inspect, text


EXPECTED_SOURCE_COLUMNS = {
    "source",
    "source_ref",
    "source_confidence",
    "source_status",
    "source_message_id",
    "source_created_at",
}

EXPECTED_NEW_INDEXES = {
    "ix_tasks_source_ref",
    "uq_tasks_source_upsert",
}


class TestTaskSourceColumns:
    def test_all_source_columns_present(self, db_session):
        """All 6 CB-TASKSYNC-001 source columns should exist on the tasks table."""
        from app.db.database import engine

        inspector = sa_inspect(engine)
        cols = {c["name"] for c in inspector.get_columns("tasks")}
        missing = EXPECTED_SOURCE_COLUMNS - cols
        assert not missing, f"Missing source columns on tasks: {missing}"

    def test_source_columns_are_nullable(self, db_session):
        """All source columns must be nullable — NULL means legacy/manual task."""
        from app.db.database import engine

        inspector = sa_inspect(engine)
        by_name = {c["name"]: c for c in inspector.get_columns("tasks")}
        for name in EXPECTED_SOURCE_COLUMNS:
            # Dialect-agnostic truthy-check: some drivers return int (1),
            # others return bool (True).
            assert bool(by_name[name].get("nullable")), (
                f"tasks.{name} must be nullable (got nullable="
                f"{by_name[name].get('nullable')!r})"
            )

    def test_new_indexes_present(self, db_session):
        """Both lookup + unique-partial indexes should be registered on tasks."""
        from app.db.database import engine

        inspector = sa_inspect(engine)
        names = {ix["name"] for ix in inspector.get_indexes("tasks")}
        missing = EXPECTED_NEW_INDEXES - names
        assert not missing, f"Missing tasks indexes: {missing}"

    def test_unique_partial_index_is_unique(self, db_session):
        """uq_tasks_source_upsert must be marked unique."""
        from app.db.database import engine

        inspector = sa_inspect(engine)
        by_name = {ix["name"]: ix for ix in inspector.get_indexes("tasks")}
        unique_ix = by_name.get("uq_tasks_source_upsert")
        assert unique_ix is not None, "uq_tasks_source_upsert missing"
        # SQLite reflection returns `unique=1`, PG returns `unique=True`; use
        # truthy-check to stay dialect-agnostic.
        assert bool(unique_ix.get("unique")), (
            "uq_tasks_source_upsert must be a UNIQUE index"
        )


class TestTaskModelRoundtrip:
    def test_can_insert_and_read_source_fields(self, db_session):
        """Task rows accept the new source-attribution fields."""
        from app.models import Task, User
        from app.models.user import UserRole

        # Minimal user (creator + assignee can be the same for this test).
        user = User(
            email="tasksync-i1@example.com",
            full_name="TaskSync I1",
            hashed_password="x",
            role=UserRole.PARENT,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        task = Task(
            created_by_user_id=user.id,
            assigned_to_user_id=user.id,
            title="I1 smoke",
            source="email_digest",
            source_ref="sha256:" + ("a" * 32),
            source_confidence=0.75,
            source_status="tentative",
            source_message_id="<gmail-id-abc@mail.gmail.com>",
            source_created_at=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        assert task.id is not None
        assert task.source == "email_digest"
        assert task.source_ref.startswith("sha256:")
        assert task.source_confidence == pytest.approx(0.75)
        assert task.source_status == "tentative"
        assert task.source_message_id.endswith("@mail.gmail.com>")
        assert task.source_created_at is not None

    def test_source_fields_default_to_null(self, db_session):
        """Tasks created without source_* should leave all source fields NULL."""
        from app.models import Task, User
        from app.models.user import UserRole

        user = User(
            email="tasksync-i1-null@example.com",
            full_name="TaskSync Null",
            hashed_password="x",
            role=UserRole.PARENT,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        task = Task(
            created_by_user_id=user.id,
            assigned_to_user_id=user.id,
            title="No-source task",
        )
        db_session.add(task)
        db_session.commit()
        db_session.refresh(task)

        assert task.source is None
        assert task.source_ref is None
        assert task.source_confidence is None
        assert task.source_status is None
        assert task.source_message_id is None
        assert task.source_created_at is None


class TestTaskSourceMigrationIdempotent:
    def _rerun_block(self, engine):
        """Execute the CB-TASKSYNC-001 migration SQL — must be a safe no-op."""
        is_sqlite = engine.dialect.name == "sqlite"
        with engine.connect() as conn:
            if is_sqlite:
                existing = {
                    row[1]
                    for row in conn.execute(text("PRAGMA table_info(tasks)")).fetchall()
                }
                specs = [
                    ("source", "VARCHAR(20)"),
                    ("source_ref", "VARCHAR(128)"),
                    ("source_confidence", "REAL"),
                    ("source_status", "VARCHAR(20)"),
                    ("source_message_id", "VARCHAR(255)"),
                    ("source_created_at", "DATETIME"),
                ]
                for col, typ in specs:
                    if col in existing:
                        continue
                    conn.execute(text(f"ALTER TABLE tasks ADD COLUMN {col} {typ}"))
            else:
                specs = [
                    ("source", "VARCHAR(20)"),
                    ("source_ref", "VARCHAR(128)"),
                    ("source_confidence", "DOUBLE PRECISION"),
                    ("source_status", "VARCHAR(20)"),
                    ("source_message_id", "VARCHAR(255)"),
                    ("source_created_at", "TIMESTAMPTZ"),
                ]
                for col, typ in specs:
                    conn.execute(text(
                        f"ALTER TABLE tasks ADD COLUMN IF NOT EXISTS {col} {typ}"
                    ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_tasks_source_ref "
                "ON tasks(source, source_ref)"
            ))
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_tasks_source_upsert "
                "ON tasks(source, source_ref, assigned_to_user_id) "
                "WHERE source IS NOT NULL"
            ))
            conn.commit()

    def _snapshot(self, engine):
        insp = sa_inspect(engine)
        return {
            "cols": sorted(c["name"] for c in insp.get_columns("tasks")),
            "indexes": sorted(i["name"] for i in insp.get_indexes("tasks")),
        }

    def test_rerun_is_noop(self, db_session):
        """Re-running the migration block multiple times must not change schema."""
        from app.db.database import engine

        before = self._snapshot(engine)
        for _ in range(3):
            self._rerun_block(engine)
        after = self._snapshot(engine)
        assert before == after

    def test_expected_schema_after_rerun(self, db_session):
        """After a rerun, all expected columns + indexes are present."""
        from app.db.database import engine

        self._rerun_block(engine)

        snap = self._snapshot(engine)
        for col in EXPECTED_SOURCE_COLUMNS:
            assert col in snap["cols"], f"Missing column {col} after rerun"
        for ix in EXPECTED_NEW_INDEXES:
            assert ix in snap["indexes"], f"Missing index {ix} after rerun"
