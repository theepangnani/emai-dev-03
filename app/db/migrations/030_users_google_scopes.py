"""users: google_granted_scopes column (#727)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "google_granted_scopes" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN google_granted_scopes VARCHAR(1024)"))
                logger.info("Added 'google_granted_scopes' column to users")
            except Exception:
                conn.rollback()
        conn.commit()
