"""Migration runner for ClassBridge (#2223).

Tracks applied migrations in a ``_migrations`` table and runs only new ones.
Each migration module must expose an ``up(conn, inspector, is_pg, settings, logger)``
function.  The runner imports them in filename order (``001_*.py``, ``002_*.py``, …).

On **first run** (when ``_migrations`` doesn't exist yet), the table is created
and every known migration is recorded as already-applied so that production
databases that already have the schema changes are not re-migrated.
"""

import importlib
import os
import pkgutil
from datetime import datetime, timezone

from sqlalchemy import text, inspect as sa_inspect


def _ensure_migrations_table(conn, is_pg):
    """Create the ``_migrations`` tracking table if it doesn't exist."""
    if is_pg:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """))
    else:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL UNIQUE,
                applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    conn.commit()


def _get_applied(conn):
    """Return the set of migration names that have already been applied."""
    rows = conn.execute(text("SELECT name FROM _migrations")).fetchall()
    return {row[0] for row in rows}


def _record_migration(conn, name):
    """Mark a migration as applied."""
    conn.execute(
        text("INSERT INTO _migrations (name, applied_at) VALUES (:name, :ts)"),
        {"name": name, "ts": datetime.now(timezone.utc)},
    )
    conn.commit()


def _discover_migrations():
    """Return a sorted list of (module_name, module) for every migration file
    in the ``app.db.migrations`` package whose name starts with a digit."""
    migrations_dir = os.path.dirname(__file__)
    results = []
    for importer, modname, _ispkg in pkgutil.iter_modules([migrations_dir]):
        # Only pick up numbered migration files (001_..., 002_..., etc.)
        if modname[0].isdigit():
            mod = importlib.import_module(f"app.db.migrations.{modname}")
            results.append((modname, mod))
    results.sort(key=lambda x: x[0])
    return results


def run_pending_migrations(engine, settings, logger):
    """Run all unapplied migrations in order.

    This function is the single entry-point called from ``main.py``.  It:

    1. Creates ``_migrations`` if missing.
    2. On first run (empty ``_migrations`` table **and** existing app tables),
       stamps all known migrations as applied without executing them — the
       production DB already has these changes.
    3. Runs any remaining unapplied migrations via their ``up()`` function.
    """
    is_pg = "sqlite" not in settings.database_url

    with engine.connect() as conn:
        inspector = sa_inspect(engine)
        table_names = inspector.get_table_names()

        # Determine if _migrations table already existed
        migrations_table_existed = "_migrations" in table_names

        _ensure_migrations_table(conn, is_pg)

        migrations = _discover_migrations()
        applied = _get_applied(conn)

        # First-run detection: _migrations was just created AND the app has
        # existing tables (i.e. this is an upgrade, not a fresh install).
        # In this case, stamp all migrations as applied without running them.
        if not migrations_table_existed and "users" in table_names and len(applied) == 0:
            logger.info(
                "First run of migration framework — stamping %d existing migrations as applied",
                len(migrations),
            )
            for name, _mod in migrations:
                _record_migration(conn, name)
            return

        # Normal path: run unapplied migrations in order
        for name, mod in migrations:
            if name in applied:
                continue
            logger.info("Running migration: %s", name)
            try:
                mod.up(conn, inspector, is_pg, settings, logger)
                _record_migration(conn, name)
                logger.info("Migration %s applied successfully", name)
            except Exception as e:
                logger.error("Migration %s failed: %s", name, e)
                raise
