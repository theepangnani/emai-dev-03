"""notification enum types: LINK_REQUEST, MATERIAL_UPLOADED, etc. (Phase 1 PostgreSQL)."""

from sqlalchemy import text


def up(conn, inspector, is_pg, settings, logger):
    if "sqlite" not in settings.database_url:
        new_notif_types = [
            "LINK_REQUEST", "MATERIAL_UPLOADED", "STUDY_GUIDE_CREATED",
            "PARENT_REQUEST", "ASSESSMENT_UPCOMING", "PROJECT_DUE",
        ]
        for ntype in new_notif_types:
            try:
                conn.execute(text(f"ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS '{ntype}'"))
                conn.commit()
            except Exception:
                conn.rollback()
