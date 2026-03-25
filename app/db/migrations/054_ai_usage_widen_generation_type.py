"""Widen ai_usage_history.generation_type from VARCHAR(20) to VARCHAR(50)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "sqlite" not in settings.database_url:
        try:
            conn.execute(text("ALTER TABLE ai_usage_history ALTER COLUMN generation_type TYPE VARCHAR(50)"))
            conn.commit()
            logger.info("Widened ai_usage_history.generation_type to VARCHAR(50)")
        except Exception:
            conn.rollback()
