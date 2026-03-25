"""users: needs_onboarding column (#412)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "needs_onboarding" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN needs_onboarding BOOLEAN DEFAULT FALSE"))
                logger.info("Added 'needs_onboarding' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
