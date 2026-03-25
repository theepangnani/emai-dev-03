"""Normalize emails to lowercase (#1045)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    try:
        conn.execute(text("UPDATE users SET email = LOWER(email) WHERE email != LOWER(email)"))
        conn.execute(text("UPDATE invites SET email = LOWER(email) WHERE email != LOWER(email)"))
        # Reset lockout state for any users who got locked out from case mismatch
        conn.execute(text(
            "UPDATE users SET failed_login_attempts = 0, locked_until = NULL "
            "WHERE failed_login_attempts > 0"
        ))
        conn.commit()
        logger.info("Normalized user emails to lowercase and reset lockout state (#1045)")
    except Exception:
        conn.rollback()
