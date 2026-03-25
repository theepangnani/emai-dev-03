"""courses: created_by_user_id, is_private, require_approval columns."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "courses" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("courses")}
        if "created_by_user_id" not in existing_cols:
            conn.execute(text("ALTER TABLE courses ADD COLUMN created_by_user_id INTEGER REFERENCES users(id)"))
            logger.info("Added 'created_by_user_id' column to courses")
        if "is_private" not in existing_cols:
            conn.execute(text("ALTER TABLE courses ADD COLUMN is_private BOOLEAN NOT NULL DEFAULT FALSE"))
            logger.info("Added 'is_private' column to courses")
        if "require_approval" not in existing_cols:
            conn.execute(text("ALTER TABLE courses ADD COLUMN require_approval BOOLEAN NOT NULL DEFAULT FALSE"))
            logger.info("Added 'require_approval' column to courses")
        conn.commit()
