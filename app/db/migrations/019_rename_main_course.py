"""Rename 'Main Course' -> 'Main Class' (#1032) and backfill is_default (#2203)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "courses" in inspector.get_table_names():
        try:
            conn.execute(text(
                "UPDATE courses SET name = 'Main Class' WHERE name = 'Main Course' AND is_default = TRUE"
            ))
            logger.info("Renamed default 'Main Course' to 'Main Class'")
        except Exception:
            conn.rollback()
        conn.commit()

    if "courses" in inspector.get_table_names():
        try:
            conn.execute(text(
                "UPDATE courses SET is_default = TRUE WHERE name = 'Main Class' AND is_default = FALSE"
            ))
            logger.info("Backfilled is_default=TRUE for existing 'Main Class' courses")
        except Exception:
            conn.rollback()
        conn.commit()
