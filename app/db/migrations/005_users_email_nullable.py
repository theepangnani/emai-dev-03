"""users: make email nullable for students created without email."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "users" in inspector.get_table_names():
        if "sqlite" not in settings.database_url:
            try:
                conn.execute(text("ALTER TABLE users ALTER COLUMN email DROP NOT NULL"))
                logger.info("Made 'email' nullable on users table")
            except Exception:
                pass  # Already nullable
            # Drop the unique constraint issue for NULL emails — PostgreSQL unique allows multiple NULLs by default
            conn.commit()
