"""users: email_verified columns (#417) and grandfather existing users."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "email_verified" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE"))
                logger.info("Added 'email_verified' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
        if "email_verified_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if "sqlite" not in settings.database_url else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN email_verified_at {col_type}"))
                logger.info("Added 'email_verified_at' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
        # Grandfather existing users as verified
        try:
            conn.execute(text("UPDATE users SET email_verified = TRUE WHERE email_verified = FALSE OR email_verified IS NULL"))
            logger.info("Grandfathered existing users as email_verified=TRUE")
        except Exception:
            conn.rollback()
        conn.commit()
