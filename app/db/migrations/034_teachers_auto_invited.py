"""teachers: auto_invited_at column (#946)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    is_pg_flag = "sqlite" not in settings.database_url
    if "teachers" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("teachers")}
        if "auto_invited_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg_flag else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE teachers ADD COLUMN auto_invited_at {col_type}"))
                logger.info("Added 'auto_invited_at' column to teachers")
            except Exception:
                conn.rollback()
        conn.commit()
