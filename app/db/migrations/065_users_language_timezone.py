"""users: preferred_language & timezone columns (#2024)."""

from sqlalchemy import text, inspect as sa_inspect


def up(conn, inspector, is_pg, settings, logger):
    try:
        inspector_ul = sa_inspect(conn.engine)
        if "users" in inspector_ul.get_table_names():
            existing_cols = {c["name"] for c in inspector_ul.get_columns("users")}
            if "preferred_language" not in existing_cols:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN preferred_language VARCHAR(10) DEFAULT 'en'"))
                    conn.commit()
                    logger.info("Added 'preferred_language' column to users (#2024)")
                except Exception:
                    conn.rollback()
            if "timezone" not in existing_cols:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN timezone VARCHAR(50) DEFAULT 'America/Toronto'"))
                    conn.commit()
                    logger.info("Added 'timezone' column to users (#2024)")
                except Exception:
                    conn.rollback()
    except Exception as e:
        logger.warning("User language/timezone migration failed (#2024): %s", e)
