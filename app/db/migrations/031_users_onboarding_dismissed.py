"""users: onboarding_dismissed_at column (#869)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    is_pg_flag = "sqlite" not in settings.database_url
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "onboarding_dismissed_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg_flag else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN onboarding_dismissed_at {col_type}"))
                logger.info("Added 'onboarding_dismissed_at' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
