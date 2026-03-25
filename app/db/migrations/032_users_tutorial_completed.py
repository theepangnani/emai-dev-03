"""users: tutorial_completed column (#1210)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "tutorial_completed" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN tutorial_completed TEXT DEFAULT '{}'"))
                logger.info("Added 'tutorial_completed' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
