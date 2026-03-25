"""xp_ledger: context_id column (#2009)."""

from sqlalchemy import text, inspect as sa_inspect


def up(conn, inspector, is_pg, settings, logger):
    try:
        inspector_local = sa_inspect(conn.engine)
        if "xp_ledger" in inspector_local.get_table_names():
            existing_cols = {c["name"] for c in inspector_local.get_columns("xp_ledger")}
            if "context_id" not in existing_cols:
                try:
                    conn.execute(text("ALTER TABLE xp_ledger ADD COLUMN context_id VARCHAR(100)"))
                    conn.commit()
                    logger.info("Added 'context_id' column to xp_ledger (#2009)")
                except Exception:
                    conn.rollback()
    except Exception as e:
        logger.warning("xp_ledger context_id migration failed (#2009): %s", e)
