"""users: unique index on username (#546)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    try:
        if "sqlite" in settings.database_url:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username_unique ON users(username)"))
        else:
            conn.execute(text("CREATE UNIQUE INDEX ix_users_username_unique ON users(username) WHERE username IS NOT NULL"))
        logger.info("Added unique index ix_users_username_unique on users.username")
    except Exception:
        conn.rollback()
    conn.commit()
