"""invites: last_resent_at column (#253)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    is_pg_flag = "sqlite" not in settings.database_url
    if "invites" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("invites")}
        if "last_resent_at" not in existing_cols:
            col_type = "TIMESTAMPTZ" if is_pg_flag else "DATETIME"
            try:
                conn.execute(text(f"ALTER TABLE invites ADD COLUMN last_resent_at {col_type}"))
                logger.info("Added 'last_resent_at' column to invites")
            except Exception:
                conn.rollback()
        conn.commit()
