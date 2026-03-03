"""Background job to periodically sync Google Classroom data.

Runs once daily at 6 AM. For each user with active Google credentials,
syncs courses, assignments, and courseWorkMaterials. Skips users whose
tokens cannot be refreshed and logs a warning.
"""

import logging
from datetime import datetime, timezone

from app.db.database import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)


async def sync_google_classrooms():
    """Sync Google Classroom data for all connected users."""
    from app.core.config import settings

    if not settings.google_classroom_enabled:
        logger.info("Google Classroom sync skipped (GOOGLE_CLASSROOM_ENABLED=false)")
        return

    from app.api.routes.google_classroom import _sync_courses_for_user

    logger.info("Starting background Google Classroom sync...")

    db = SessionLocal()
    synced_users = 0
    failed_users = 0

    try:
        # Find all users with Google tokens
        users = (
            db.query(User)
            .filter(
                User.google_access_token.isnot(None),
                User.is_active == True,  # noqa: E712
            )
            .all()
        )

        logger.info(f"Found {len(users)} users with Google connections")

        for user in users:
            try:
                result = _sync_courses_for_user(user, db)
                courses = result["courses"]
                materials = result["materials_synced"]
                assignments = result["assignments_synced"]
                synced_users += 1
                if courses or materials or assignments:
                    logger.info(
                        f"Background sync for user {user.id}: "
                        f"{len(courses)} courses, {materials} new materials, "
                        f"{assignments} new assignments"
                    )
            except Exception as e:
                failed_users += 1
                logger.warning(
                    f"Background sync failed for user {user.id}: {e}"
                )
                db.rollback()

        logger.info(
            f"Background Google sync complete | "
            f"synced={synced_users} | failed={failed_users}"
        )

    except Exception as e:
        logger.error(f"Background Google sync job failed: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
