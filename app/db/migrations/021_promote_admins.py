"""One-time: promote users to admin."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    for admin_email in ["theepang@gmail.com", "clazzbridge@gmail.com"]:
        try:
            row = conn.execute(text(
                "SELECT id, roles FROM users WHERE email = :email "
                "AND (roles IS NULL OR roles NOT LIKE '%admin%')"
            ), {"email": admin_email}).first()
            if row:
                existing = row[1] or ""
                new_roles = "admin," + existing if existing else "admin"
                conn.execute(text(
                    "UPDATE users SET role = 'ADMIN', roles = :roles WHERE id = :id"
                ), {"roles": new_roles, "id": row[0]})
                logger.info("Promoted %s to admin", admin_email)
        except Exception:
            pass  # User may not exist yet in this environment

    conn.commit()
