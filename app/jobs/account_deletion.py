"""Daily job: anonymize and purge user accounts whose scheduled deletion date has passed.

GDPR right to erasure — runs daily at 2 AM.

The anonymization is idempotent: running it twice on the same user is safe.
The user row is kept (for FK integrity) but all PII is scrubbed.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.user import User

logger = logging.getLogger(__name__)

_DELETED_NAME = "[Deleted User]"


def _anonymize_user(user: User) -> None:
    """Scrub all PII from a user record (idempotent)."""
    user.email = f"deleted_{user.id}@deleted.local"
    user.username = None
    user.full_name = _DELETED_NAME
    user.hashed_password = None
    user.google_id = None
    user.google_access_token = None
    user.google_refresh_token = None
    user.google_granted_scopes = None
    user.consent_preferences = None
    user.is_active = False
    # Clear deletion schedule fields (anonymization is the final state)
    user.deletion_requested_at = None
    user.deletion_scheduled_for = None


async def process_scheduled_deletions() -> None:
    """Find users whose deletion date has passed and anonymize them.

    Runs daily at 2 AM via APScheduler.
    """
    logger.info("Running scheduled account deletion job...")

    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        now_naive = now.replace(tzinfo=None)

        # Find users scheduled for deletion
        users_to_delete = db.query(User).filter(
            User.deletion_scheduled_for.isnot(None),
        ).all()

        processed = 0
        for user in users_to_delete:
            try:
                # Compare as naive UTC to handle SQLite vs PostgreSQL tz differences
                sched = user.deletion_scheduled_for
                if sched is None:
                    continue
                sched_naive = sched.replace(tzinfo=None)
                if sched_naive > now_naive:
                    continue  # Not yet due

                # Skip already-anonymized users (idempotent guard)
                if not user.is_active and user.full_name == _DELETED_NAME:
                    # Clear schedule so we don't keep re-checking
                    user.deletion_requested_at = None
                    user.deletion_scheduled_for = None
                    db.commit()
                    continue

                logger.info("Anonymizing user id=%s (scheduled_for=%s)", user.id, sched_naive)
                _anonymize_user(user)
                db.commit()
                processed += 1
            except Exception as e:
                logger.error("Failed to anonymize user id=%s: %s", user.id, e, exc_info=True)
                db.rollback()

        logger.info("Account deletion job complete | processed=%s", processed)

    except Exception as e:
        logger.error("Account deletion job failed: %s", e, exc_info=True)
        db.rollback()
    finally:
        db.close()
