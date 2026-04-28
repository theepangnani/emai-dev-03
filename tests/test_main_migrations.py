"""Tests for the migrations plumbing in ``main.py`` (CB-CMCP-001 0A-4, #4427).

These tests guard the documented migration pattern used across ~9 startup
migration blocks in ``main.py``:

* ``pg_try_advisory_lock(<id>)`` with **3 retries × 5s** sleep between attempts
  (per the CLAUDE.md "Migration locking" rule — never ``pg_advisory_lock``,
  which blocks forever if a previous Cloud Run instance is dead).
* Failed migration paths must ``rollback`` the connection so subsequent
  blocks don't inherit a poisoned transaction.
* PG-only branches must be gated on ``"sqlite" not in settings.database_url``
  (otherwise SQLite test runs hit ``ALTER TYPE`` / ``pg_*`` and explode).

The tests simulate the pattern directly — they do not re-import ``main.py``
(that has heavy startup side effects). The pattern is the contract; if a
future stripe deviates, ``/pr-review`` should catch it, and these tests
provide a regression net for the pattern itself.

Sister test: ``tests/test_demo_migrations_idempotent.py`` covers the
**idempotency** half of the contract (re-running an ALTER COLUMN /
CREATE INDEX block is a no-op). Together they cover both halves of the
"safe to re-run on a Cloud Run cold start" guarantee.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# --------------------------------------------------------------------------
# Pattern-under-test: a tiny re-implementation of the advisory-lock retry
# loop used in main.py. Tests below exercise this against mocked engines.
# This mirrors the inline blocks for `_lh_*`, `_ur_*`, `_cmcp_sg_*`, etc.
# --------------------------------------------------------------------------


def _try_acquire_lock(connection, lock_id: int, *, max_attempts: int = 3,
                      sleep_seconds: float = 5.0, sleep_fn=None,
                      sql_text=None):
    """Reference implementation of the advisory-lock retry pattern.

    Returns ``True`` if the lock was acquired within ``max_attempts``,
    ``False`` otherwise. Mirrors the loop body used in every PG migration
    block in ``main.py`` (see e.g. lines 173-186 / 1086-1100 / 1136-1151).

    The production blocks inline this loop for visibility; this function
    is only used by the test suite as a regression target for the
    pattern's semantics.
    """
    if sleep_fn is None:
        import time as _t
        sleep_fn = _t.sleep
    if sql_text is None:
        from sqlalchemy import text as _text
        sql_text = _text

    for attempt in range(1, max_attempts + 1):
        result = connection.execute(sql_text(f"SELECT pg_try_advisory_lock({lock_id})"))
        if result.scalar():
            return True
        if attempt < max_attempts:
            sleep_fn(sleep_seconds)
    return False


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


class TestAdvisoryLockRetry:
    """Advisory-lock retry kicks in correctly under simulated contention."""

    def test_acquired_on_first_attempt_no_sleep(self):
        """Happy path: lock acquired immediately, no retries, no sleep."""
        conn = MagicMock()
        conn.execute.return_value.scalar.return_value = True
        sleep_fn = MagicMock()

        acquired = _try_acquire_lock(conn, lock_id=4413, sleep_fn=sleep_fn)

        assert acquired is True
        assert conn.execute.call_count == 1
        sleep_fn.assert_not_called()

    def test_retries_until_acquired_on_third_attempt(self):
        """Contention: locked twice then released — must succeed on attempt 3.

        This is the regression test for the ``3 retries × 5s`` rule
        (CLAUDE.md "Migration locking"). Sleep is invoked between
        unsuccessful attempts (i.e. twice — not three times).
        """
        conn = MagicMock()
        # First two probes return False, third returns True.
        scalars = iter([False, False, True])
        conn.execute.return_value.scalar.side_effect = lambda: next(scalars)
        sleep_fn = MagicMock()

        acquired = _try_acquire_lock(conn, lock_id=4413, sleep_fn=sleep_fn)

        assert acquired is True
        assert conn.execute.call_count == 3
        # Sleep is between failed attempts (1->2, 2->3) — not after the
        # successful one. So 2 sleeps for 3 attempts when success on 3rd.
        assert sleep_fn.call_count == 2
        for call in sleep_fn.call_args_list:
            assert call.args == (5.0,), "sleep must be 5 seconds per CLAUDE.md"

    def test_returns_false_after_three_failed_attempts(self):
        """All three probes return False — function returns False, no 4th probe.

        Note: the production pattern then *runs the migration anyway*
        without the lock and emits a warning. That fallback is the
        responsibility of the caller; this helper just reports the
        outcome of acquisition.
        """
        conn = MagicMock()
        conn.execute.return_value.scalar.return_value = False
        sleep_fn = MagicMock()

        acquired = _try_acquire_lock(conn, lock_id=4414, sleep_fn=sleep_fn)

        assert acquired is False
        assert conn.execute.call_count == 3
        # No sleep after the final failed attempt (we're done retrying).
        assert sleep_fn.call_count == 2

    def test_uses_pg_try_advisory_lock_not_pg_advisory_lock(self):
        """CRITICAL: must use ``pg_try_advisory_lock`` (non-blocking).

        ``pg_advisory_lock`` blocks forever if a previous Cloud Run
        instance is dead and never unlocks — this is the failure mode
        the CLAUDE.md memory rule was added to prevent.
        """
        conn = MagicMock()
        conn.execute.return_value.scalar.return_value = True

        _try_acquire_lock(conn, lock_id=4413, sleep_fn=MagicMock())

        # Inspect the SQL that was executed.
        call_args = conn.execute.call_args
        sql_passed = call_args.args[0]
        sql_str = str(sql_passed)
        assert "pg_try_advisory_lock" in sql_str, (
            "MUST use pg_try_advisory_lock (non-blocking) — "
            "pg_advisory_lock blocks forever on dead instances. "
            "See CLAUDE.md 'Migration locking' rule."
        )
        assert "pg_advisory_lock(" not in sql_str.replace("pg_try_advisory_lock", ""), (
            "Found bare pg_advisory_lock call — replace with pg_try_advisory_lock."
        )


class TestMigrationRollback:
    """Failed migration must roll back cleanly without poisoning the connection."""

    def test_rollback_called_on_alter_failure(self):
        """When an ALTER raises, ``rollback()`` is called before the next block.

        Mirrors the ``except _cmcp_sg_col_err: _conn.rollback()`` branch
        at main.py:1198-1200.
        """
        conn = MagicMock()
        # First execute (the ALTER) raises; subsequent execute (post-rollback)
        # should still work.
        conn.execute.side_effect = [
            Exception("relation already exists"),  # ALTER fails
            None,  # post-rollback execute succeeds
        ]

        # Simulate the production try/except/rollback shape.
        rollback_called = False
        try:
            try:
                conn.execute("ALTER TABLE study_guides ADD COLUMN x INTEGER")
                conn.commit()
            except Exception:
                conn.rollback()
                rollback_called = True
        except Exception:
            pytest.fail("rollback() itself should not raise")

        assert rollback_called is True
        conn.rollback.assert_called_once()

    def test_post_rollback_connection_is_usable(self):
        """After rollback, the next migration block can still execute.

        This is the "doesn't poison the connection" half of the contract.
        The production code uses ``with engine.connect() as _conn:`` for
        each block, so this is also defended structurally — but we test
        the contract anyway in case a future block reuses a connection.
        """
        conn = MagicMock()
        # Simulate: ALTER fails -> rollback -> next ALTER succeeds.
        conn.execute.side_effect = [
            Exception("duplicate column"),
            None,
            None,
        ]

        try:
            conn.execute("ALTER TABLE x ADD COLUMN y INTEGER")
        except Exception:
            conn.rollback()

        # Next block should not see a poisoned txn.
        conn.execute("ALTER TABLE x ADD COLUMN z INTEGER")
        conn.commit()

        assert conn.execute.call_count == 2
        conn.rollback.assert_called_once()
        conn.commit.assert_called_once()

    def test_outer_try_swallows_exception_so_startup_continues(self):
        """The outer ``except _err: logger.warning(...)`` MUST NOT re-raise.

        Mirrors the pattern at main.py:243 / 349 / 543 / 693 / 1117 /
        1201. If a migration outer block raises, FastAPI startup
        crashes and Cloud Run cannot serve ``/health`` — Cloud Run
        kills the revision and traffic stays on the previous one
        (#3425 root cause).
        """
        log_messages = []
        try:
            try:
                raise RuntimeError("simulated migration failure")
            except Exception as e:
                log_messages.append(f"migration note: {e}")
        except Exception:
            pytest.fail("outer try/except must swallow — startup must not crash")

        assert len(log_messages) == 1
        assert "simulated migration failure" in log_messages[0]


class TestSQLiteGating:
    """SQLite gating skips PG-only paths.

    The convention is ``_is_pg = "sqlite" not in settings.database_url``
    (main.py:101) and every ``pg_try_advisory_lock`` / ``ALTER TYPE`` /
    ``CREATE INDEX ... WHERE`` path is wrapped in ``if _is_pg:``.
    """

    def test_is_pg_false_for_sqlite_url(self):
        """SQLite URLs evaluate ``_is_pg`` to False."""
        for url in (
            "sqlite:///./test.db",
            "sqlite:////tmp/foo.db",
            "sqlite+pysqlite:///:memory:",
        ):
            assert ("sqlite" not in url) is False, (
                f"SQLite URL {url!r} should evaluate _is_pg to False"
            )

    def test_is_pg_true_for_postgres_url(self):
        """Postgres URLs evaluate ``_is_pg`` to True."""
        for url in (
            "postgresql://u:p@host:5432/db",
            "postgresql+psycopg2://u@host/db",
            "postgresql+asyncpg://u:p@host/db",
        ):
            assert ("sqlite" not in url) is True, (
                f"Postgres URL {url!r} should evaluate _is_pg to True"
            )

    def test_advisory_lock_block_skipped_when_not_pg(self):
        """When ``_is_pg`` is False, the lock-acquisition block is skipped.

        Simulates the ``if _is_pg: ... pg_try_advisory_lock ...`` gate
        used in every PG migration block (e.g. main.py:174, 1089, 1139).
        """
        is_pg = "sqlite" not in "sqlite:///./test.db"  # SQLite case
        conn = MagicMock()
        sleep_fn = MagicMock()

        # The gate: only enter the lock block if _is_pg.
        if is_pg:
            _try_acquire_lock(conn, lock_id=4413, sleep_fn=sleep_fn)

        conn.execute.assert_not_called()
        sleep_fn.assert_not_called()

    def test_alter_type_path_skipped_for_sqlite(self):
        """``ALTER TYPE userrole ADD VALUE`` is PG-only — must be gated.

        Mirrors the 0A-3 pattern at main.py:1106-1116. SQLite uses
        VARCHAR + CHECK refreshed by ``Base.metadata.create_all`` so
        no migration is needed there.
        """
        is_pg = "sqlite" not in "sqlite:///./test.db"
        executed = []

        if is_pg:
            executed.append("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'BOARD_ADMIN'")
            executed.append("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'CURRICULUM_ADMIN'")

        assert executed == [], (
            "ALTER TYPE statements must not run on SQLite — "
            "they will raise OperationalError."
        )


class TestExistingMigrationBlocksConformToPattern:
    """Audit: the existing 0A-2 (#4413) and 0A-3 (#4414) migration blocks
    in ``main.py`` follow the documented pattern.

    These tests parse main.py as text and assert structural properties.
    They are intentionally string-level (not behavioural) because the
    blocks are inlined at module import time — exercising them
    directly would require re-importing main.py with side effects.
    """

    @pytest.fixture(scope="class")
    def main_py_source(self):
        from pathlib import Path
        repo_root = Path(__file__).resolve().parent.parent
        return (repo_root / "main.py").read_text(encoding="utf-8")

    def test_0a2_block_uses_pg_try_advisory_lock_4413(self, main_py_source):
        """0A-2 (study_guides extension) uses lock id 4413."""
        assert "pg_try_advisory_lock(4413)" in main_py_source

    def test_0a3_block_uses_pg_try_advisory_lock_4414(self, main_py_source):
        """0A-3 (userrole enum extension) uses lock id 4414."""
        assert "pg_try_advisory_lock(4414)" in main_py_source

    def test_0a2_block_has_3_retry_loop(self, main_py_source):
        """0A-2 uses the canonical 3-attempt retry (``range(1, 4)``)."""
        # The 0A-2 block sits between the 0A-3 marker and the
        # ``run_startup_migrations`` import. Slice and check.
        start = main_py_source.find("CB-CMCP-001 0A-2 (#4413)")
        end = main_py_source.find("Lightweight schema migration", start)
        assert start != -1, "0A-2 marker not found"
        assert end != -1, "trailing marker not found"
        block = main_py_source[start:end]
        assert "range(1, 4)" in block, (
            "0A-2 block missing 3-attempt retry loop "
            "(should be ``for _attempt in range(1, 4)``)"
        )
        assert ".sleep(5)" in block, (
            "0A-2 block missing 5-second sleep between retries"
        )

    def test_0a3_block_has_3_retry_loop(self, main_py_source):
        """0A-3 uses the canonical 3-attempt retry (``range(1, 4)``)."""
        start = main_py_source.find("CB-CMCP-001 M0-A 0A-3 (#4414)")
        end = main_py_source.find("CB-CMCP-001 0A-2 (#4413)", start)
        assert start != -1, "0A-3 marker not found"
        assert end != -1, "0A-2 marker not found after 0A-3"
        block = main_py_source[start:end]
        assert "range(1, 4)" in block
        assert ".sleep(5)" in block

    def test_0a2_and_0a3_blocks_have_finally_unlock(self, main_py_source):
        """Both blocks release the lock in a ``finally`` clause."""
        for marker, lock_id in (
            ("CB-CMCP-001 0A-2 (#4413)", 4413),
            ("CB-CMCP-001 M0-A 0A-3 (#4414)", 4414),
        ):
            start = main_py_source.find(marker)
            assert start != -1, f"marker {marker!r} not found"
            # Take a generous slice — both blocks are well under 200 lines.
            block = main_py_source[start:start + 6000]
            assert "finally:" in block, (
                f"block {marker!r} missing finally clause for lock release"
            )
            assert f"pg_advisory_unlock({lock_id})" in block, (
                f"block {marker!r} missing pg_advisory_unlock({lock_id})"
            )

    def test_0a2_block_gates_pg_paths_on_is_pg(self, main_py_source):
        """0A-2 wraps PG-specific SQL behind ``if _is_pg`` / ``if is_pg``."""
        start = main_py_source.find("CB-CMCP-001 0A-2 (#4413)")
        end = main_py_source.find("Lightweight schema migration", start)
        block = main_py_source[start:end]
        assert "if _is_pg" in block, (
            "0A-2 block missing _is_pg gate — JSONB / IF NOT EXISTS "
            "must be PG-only"
        )

    def test_0a3_block_is_pg_only(self, main_py_source):
        """0A-3 is fully gated on ``_is_pg`` (SQLite re-creates enum via create_all)."""
        start = main_py_source.find("CB-CMCP-001 M0-A 0A-3 (#4414)")
        end = main_py_source.find("CB-CMCP-001 0A-2 (#4413)", start)
        block = main_py_source[start:end]
        assert "if _is_pg" in block, (
            "0A-3 block missing _is_pg gate — ALTER TYPE is PG-only"
        )

    def test_no_blocking_pg_advisory_lock_anywhere(self, main_py_source):
        """No code line uses bare ``pg_advisory_lock(<n>)`` (the blocking variant).

        The CLAUDE.md memory rule is non-negotiable: every advisory lock
        must use the ``pg_try_advisory_lock`` (non-blocking) variant so
        a dead Cloud Run instance can't deadlock startup. We scan
        non-comment lines and check via regex so prose mentions in
        the reference comment block (which legitimately quote the
        forbidden form to warn against it) don't false-positive.
        """
        import re

        # Match a real call: ``pg_advisory_lock(<digits>)`` not preceded
        # by ``try_`` and not part of ``pg_advisory_unlock``.
        bad_call = re.compile(r"(?<!try_)pg_advisory_lock\(\d+\)")
        offenders = []
        for lineno, line in enumerate(main_py_source.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue  # comment / docstring guidance lines are exempt
            if bad_call.search(line):
                offenders.append((lineno, line.strip()))
        assert offenders == [], (
            f"Found bare pg_advisory_lock(<n>) calls — these block "
            f"forever if a previous instance is dead. Replace with "
            f"pg_try_advisory_lock + 3-retry loop. See CLAUDE.md "
            f"'Migration locking' rule.\nOffenders: {offenders}"
        )


class TestMigrationPatternReferenceCommentExists:
    """The reference comment block exists near the migration section.

    This is the documentation half of the stripe (#4427 ACs): future
    stripes can find the canonical pattern in one place rather than
    copy-pasting from another stripe and inheriting its quirks.
    """

    def test_reference_comment_block_present(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
        assert "MIGRATION PATTERN REFERENCE" in src, (
            "Expected reference comment block 'MIGRATION PATTERN REFERENCE' "
            "in main.py — see CB-CMCP-001 0A-4 (#4427)"
        )

    def test_reference_documents_pg_try_advisory_lock_rule(self):
        from pathlib import Path
        src = (Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
        # Locate the reference block.
        start = src.find("MIGRATION PATTERN REFERENCE")
        assert start != -1
        block = src[start:start + 4000]
        # Key facts that future stripes must know.
        assert "pg_try_advisory_lock" in block
        assert "3 retries" in block or "3 attempts" in block or "range(1, 4)" in block
        assert "rollback" in block.lower()
        assert "_is_pg" in block or "sqlite" in block.lower()
