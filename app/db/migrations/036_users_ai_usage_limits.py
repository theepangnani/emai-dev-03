"""users: AI usage limit columns (#1118, #1117, #1119) + backfill (#1400)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    # Multiple duplicate blocks existed in original — consolidated here
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "ai_usage_limit" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN ai_usage_limit INTEGER DEFAULT 10"))
                logger.info("Added 'ai_usage_limit' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

        if "ai_usage_count" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN ai_usage_count INTEGER DEFAULT 0"))
                logger.info("Added 'ai_usage_count' column to users")
            except Exception:
                conn.rollback()
        conn.commit()

    # Backfill NULL ai_usage columns (#1400)
    try:
        conn.execute(text("UPDATE users SET ai_usage_count = 0 WHERE ai_usage_count IS NULL"))
        conn.execute(text("UPDATE users SET ai_usage_limit = 10 WHERE ai_usage_limit IS NULL"))
        conn.commit()
    except Exception:
        conn.rollback()
