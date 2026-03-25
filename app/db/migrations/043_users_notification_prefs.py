"""users: notification_preferences column (#966)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "notification_preferences" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN notification_preferences TEXT"))
                logger.info("Added 'notification_preferences' column to users (#966)")
            except Exception:
                conn.rollback()
        conn.commit()
