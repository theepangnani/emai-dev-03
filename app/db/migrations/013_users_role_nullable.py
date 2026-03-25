"""users: make role column nullable (#412)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "sqlite" not in settings.database_url:
        if "users" in inspector.get_table_names():
            try:
                conn.execute(text("ALTER TABLE users ALTER COLUMN role DROP NOT NULL"))
                logger.info("Made 'role' nullable on users table")
            except Exception:
                conn.rollback()
            conn.commit()
