"""notes: highlights_json column (#1185)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    try:
        conn.execute(text("ALTER TABLE notes ADD COLUMN highlights_json TEXT"))
        conn.commit()
    except Exception:
        conn.rollback()
