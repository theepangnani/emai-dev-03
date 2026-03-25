"""users: storage limit columns (#1007)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "storage_used_bytes" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN storage_used_bytes BIGINT DEFAULT 0"))
                logger.info("Added storage_used_bytes")
            except Exception:
                conn.rollback()
        conn.commit()
        if "storage_limit_bytes" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN storage_limit_bytes BIGINT DEFAULT 104857600"))
                logger.info("Added storage_limit_bytes")
            except Exception:
                conn.rollback()
        conn.commit()
        if "upload_limit_bytes" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN upload_limit_bytes INTEGER DEFAULT 10485760"))
                logger.info("Added upload_limit_bytes")
            except Exception:
                conn.rollback()
        conn.commit()
