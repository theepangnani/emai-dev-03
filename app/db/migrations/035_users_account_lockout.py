"""users: account lockout columns (#796)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    is_pg_flag = "sqlite" not in settings.database_url
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "failed_login_attempts" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0"))
                logger.info("Added 'failed_login_attempts' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

        if "locked_until" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg_flag else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN locked_until {col_type}"))
                logger.info("Added 'locked_until' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

        if "last_failed_login" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg_flag else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN last_failed_login {col_type}"))
                logger.info("Added 'last_failed_login' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
