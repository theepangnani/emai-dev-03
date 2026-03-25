"""CASL email consent columns (#2022)."""

from sqlalchemy import text, inspect as sa_inspect


def up(conn, inspector, is_pg, settings, logger):
    try:
        inspector_casl = sa_inspect(conn.engine)
        if "users" in inspector_casl.get_table_names():
            existing_cols = {c["name"] for c in inspector_casl.get_columns("users")}
            if "email_marketing_consent" not in existing_cols:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN email_marketing_consent BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    logger.info("Added 'email_marketing_consent' column to users (#2022)")
                except Exception:
                    conn.rollback()
            if "email_consent_date" not in existing_cols:
                col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN email_consent_date {col_type}"))
                    conn.commit()
                    logger.info("Added 'email_consent_date' column to users (#2022)")
                except Exception:
                    conn.rollback()
    except Exception as e:
        logger.warning("CASL consent columns migration failed (#2022): %s", e)
