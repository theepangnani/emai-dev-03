"""teachers: is_platform_user column (#58)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "teachers" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("teachers")}
        if "is_platform_user" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE teachers ADD COLUMN is_platform_user BOOLEAN DEFAULT TRUE"))
                logger.info("Added 'is_platform_user' column to teachers")
            except Exception:
                conn.rollback()
        conn.commit()
