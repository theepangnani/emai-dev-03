"""users: username column (Phase 1 New Workflow)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "username" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(100)"))
                logger.info("Added 'username' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
