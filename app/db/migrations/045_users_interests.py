"""users: interests column (#1437, #1440)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "users" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("users")}
        if "interests" not in existing_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN interests TEXT"))
                logger.info("Added 'interests' column to users (#1437)")
            except Exception:
                conn.rollback()
            conn.commit()
