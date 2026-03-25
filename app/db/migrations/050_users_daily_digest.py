"""users: daily_digest_enabled column (#1406)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "daily_digest_enabled" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN daily_digest_enabled BOOLEAN DEFAULT FALSE"))
                logger.info("Added 'daily_digest_enabled' column to users (#1406)")
            except Exception:
                conn.rollback()
        conn.commit()
