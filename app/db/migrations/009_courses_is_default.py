"""courses: is_default column."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "courses" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("courses")}
        if "is_default" not in existing_cols:
            conn.execute(text("ALTER TABLE courses ADD COLUMN is_default BOOLEAN NOT NULL DEFAULT FALSE"))
            logger.info("Added 'is_default' column to courses")
        conn.commit()
