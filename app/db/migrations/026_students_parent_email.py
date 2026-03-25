"""students: parent_email column (Phase 1 New Workflow)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "students" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("students")}
        if "parent_email" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE students ADD COLUMN parent_email VARCHAR(255)"))
                logger.info("Added 'parent_email' column to students")
            except Exception:
                conn.rollback()
        conn.commit()
