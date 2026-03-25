"""users: change @classbridge.ca system emails to gmail (#2255, #2256)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    try:
        conn.execute(text(
            "UPDATE users SET email = 'clazzbridge@gmail.com' WHERE email = 'system@classbridge.ca'"
        ))
        conn.commit()
    except Exception:
        conn.rollback()
