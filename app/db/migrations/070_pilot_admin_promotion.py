"""users: promote pilot-admin to admin and fix orphaned email (#2265)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    try:
        # If pilot-admin still exists with old email, promote to admin
        row = conn.execute(text(
            "SELECT id, roles FROM users WHERE email = 'pilot-admin@classbridge.ca' "
            "AND (roles IS NULL OR roles NOT LIKE '%admin%')"
        )).first()
        if row:
            existing = row[1] or ""
            new_roles = "admin," + existing if existing else "admin"
            conn.execute(text(
                "UPDATE users SET role = 'ADMIN', roles = :roles WHERE id = :id"
            ), {"roles": new_roles, "id": row[0]})
            logger.info("Promoted pilot-admin@classbridge.ca to admin (#2265)")
        conn.commit()
    except Exception:
        conn.rollback()
