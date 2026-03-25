"""One-time data fix: correct known invalid email (#408)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    try:
        conn.execute(text(
            "UPDATE users SET email = 'haashinik30@gmail.com' WHERE email = 'haashinik30@gmailcom'"
        ))
        conn.execute(text(
            "UPDATE invites SET email = 'haashinik30@gmail.com' WHERE email = 'haashinik30@gmailcom'"
        ))
        conn.commit()
    except Exception:
        conn.rollback()
