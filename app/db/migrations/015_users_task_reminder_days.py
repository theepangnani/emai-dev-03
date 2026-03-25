"""users: task_reminder_days column."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "task_reminder_days" not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN task_reminder_days VARCHAR(50) DEFAULT '1,3'"))
            logger.info("Added 'task_reminder_days' column to users")
        conn.commit()
