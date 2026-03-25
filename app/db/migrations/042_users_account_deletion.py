"""users: account deletion columns (#964)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    is_pg_flag = "sqlite" not in settings.database_url
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "deletion_requested_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg_flag else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN deletion_requested_at {col_type}"))
                logger.info("Added 'deletion_requested_at' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

        if "deletion_confirmed_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg_flag else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN deletion_confirmed_at {col_type}"))
                logger.info("Added 'deletion_confirmed_at' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

        if "is_deleted" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE"))
                logger.info("Added 'is_deleted' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
