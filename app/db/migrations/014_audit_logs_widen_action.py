"""audit_logs: widen action column from VARCHAR(20) to VARCHAR(50)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "audit_logs" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("audit_logs")}
        if "action" in existing_cols:
            if "sqlite" not in settings.database_url:
                try:
                    conn.execute(text("ALTER TABLE audit_logs ALTER COLUMN action TYPE VARCHAR(50)"))
                    logger.info("Widened audit_logs.action to VARCHAR(50)")
                except Exception:
                    conn.rollback()
        conn.commit()
