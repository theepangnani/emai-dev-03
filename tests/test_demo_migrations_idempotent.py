"""Idempotency test for the UTDF / demo_sessions migration blocks (CB-DEMO-001, #3624).

Re-running the startup migration logic (column ALTERs + CREATE INDEX)
must not raise and must not change the inspected schema.
"""
from __future__ import annotations

from sqlalchemy import inspect as sa_inspect, text


_DEMO_INDEX_SQL = [
    ("idx_demo_sessions_verification_token_hash",
     "CREATE INDEX IF NOT EXISTS idx_demo_sessions_verification_token_hash "
     "ON demo_sessions(verification_token_hash)"),
    ("idx_demo_sessions_source_ip_hash",
     "CREATE INDEX IF NOT EXISTS idx_demo_sessions_source_ip_hash "
     "ON demo_sessions(source_ip_hash)"),
    ("idx_demo_sessions_verified_ts",
     "CREATE INDEX IF NOT EXISTS idx_demo_sessions_verified_ts "
     "ON demo_sessions(verified_ts) WHERE verified = TRUE"),
    ("idx_demo_sessions_email_hash",
     "CREATE INDEX IF NOT EXISTS idx_demo_sessions_email_hash "
     "ON demo_sessions(email_hash)"),
]


def _snapshot_schema(engine):
    insp = sa_inspect(engine)
    return {
        "tables": sorted(insp.get_table_names()),
        "demo_sessions_columns": sorted(
            c["name"] for c in insp.get_columns("demo_sessions")
        ),
        "demo_sessions_indexes": sorted(
            i["name"] for i in insp.get_indexes("demo_sessions")
        ),
    }


class TestMigrationIdempotency:
    def test_indexes_rerun_without_error(self, db_session):
        """Re-running CREATE INDEX IF NOT EXISTS is a no-op."""
        from app.db.database import engine

        before = _snapshot_schema(engine)

        # Simulate re-running the index block several times.
        for _ in range(3):
            with engine.connect() as conn:
                for _name, sql in _DEMO_INDEX_SQL:
                    conn.execute(text(sql))
                conn.commit()

        after = _snapshot_schema(engine)
        assert before == after

    def test_expected_indexes_present_after_rerun(self, db_session):
        """All four demo_sessions indexes exist after a rerun of the block."""
        from app.db.database import engine

        with engine.connect() as conn:
            for _name, sql in _DEMO_INDEX_SQL:
                conn.execute(text(sql))
            conn.commit()

        insp = sa_inspect(engine)
        names = {i["name"] for i in insp.get_indexes("demo_sessions")}
        for expected in (
            "idx_demo_sessions_email_hash",
            "idx_demo_sessions_verification_token_hash",
            "idx_demo_sessions_source_ip_hash",
            "idx_demo_sessions_verified_ts",
        ):
            assert expected in names, f"Missing {expected} after rerun"

    def test_create_table_if_not_exists_is_noop(self, db_session):
        """Re-issuing the demo_sessions CREATE TABLE IF NOT EXISTS is a no-op."""
        from app.core.config import settings
        from app.db.database import engine

        before = _snapshot_schema(engine)

        is_pg = "sqlite" not in settings.database_url
        if is_pg:
            ddl = """
                CREATE TABLE IF NOT EXISTS demo_sessions (
                    id UUID PRIMARY KEY
                )
            """
        else:
            ddl = """
                CREATE TABLE IF NOT EXISTS demo_sessions (
                    id VARCHAR(36) PRIMARY KEY
                )
            """

        with engine.connect() as conn:
            conn.execute(text(ddl))
            conn.commit()

        after = _snapshot_schema(engine)
        assert before == after
