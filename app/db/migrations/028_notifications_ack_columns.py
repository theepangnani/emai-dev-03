"""notifications: ACK columns (Phase 1 New Workflow)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    is_pg_flag = "sqlite" not in settings.database_url
    if "notifications" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("notifications")}

        if "requires_ack" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN requires_ack BOOLEAN DEFAULT FALSE"))
                logger.info("Added 'requires_ack' column to notifications")
            except Exception:
                conn.rollback()
        conn.commit()

        if "acked_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg_flag else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE notifications ADD COLUMN acked_at {col_type}"))
                logger.info("Added 'acked_at' column to notifications")
            except Exception:
                conn.rollback()
        conn.commit()

        if "source_type" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN source_type VARCHAR(50)"))
                logger.info("Added 'source_type' column to notifications")
            except Exception:
                conn.rollback()
        conn.commit()

        if "source_id" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN source_id INTEGER"))
                logger.info("Added 'source_id' column to notifications")
            except Exception:
                conn.rollback()
        conn.commit()

        if "next_reminder_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg_flag else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE notifications ADD COLUMN next_reminder_at {col_type}"))
                logger.info("Added 'next_reminder_at' column to notifications")
            except Exception:
                conn.rollback()
        conn.commit()

        if "reminder_count" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN reminder_count INTEGER DEFAULT 0"))
                logger.info("Added 'reminder_count' column to notifications")
            except Exception:
                conn.rollback()
        conn.commit()
