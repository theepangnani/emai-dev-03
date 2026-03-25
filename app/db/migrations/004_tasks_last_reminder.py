"""tasks: last_reminder_sent_at column (#876)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "tasks" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("tasks")}
        if "last_reminder_sent_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE tasks ADD COLUMN last_reminder_sent_at {col_type}"))
                logger.info("Added 'last_reminder_sent_at' column to tasks")
            except Exception:
                conn.rollback()
        conn.commit()
