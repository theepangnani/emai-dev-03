"""Account deletion and data anonymization service.

Handles soft-delete with 30-day grace period, email confirmation,
and PII anonymization for privacy compliance.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

# Grace period before permanent anonymization (days)
DELETION_GRACE_PERIOD_DAYS = 30


def request_deletion(db: Session, user: User) -> None:
    """Mark an account for deletion. Does NOT yet anonymize data."""
    user.deletion_requested_at = datetime.now(timezone.utc)
    user.deletion_confirmed_at = None  # Reset if re-requesting
    db.commit()
    logger.info("Deletion requested for user %s (%s)", user.id, user.email)


def confirm_deletion(db: Session, user: User) -> None:
    """Confirm a pending deletion request. Starts the 30-day grace period."""
    now = datetime.now(timezone.utc)
    user.deletion_confirmed_at = now
    user.is_active = False  # Immediately deactivate
    db.commit()
    logger.info(
        "Deletion confirmed for user %s. Anonymization scheduled for %s",
        user.id,
        now + timedelta(days=DELETION_GRACE_PERIOD_DAYS),
    )


def cancel_deletion(db: Session, user: User) -> None:
    """Cancel a pending deletion request and reactivate."""
    user.deletion_requested_at = None
    user.deletion_confirmed_at = None
    user.is_active = True
    user.is_deleted = False
    db.commit()
    logger.info("Deletion cancelled for user %s", user.id)


def anonymize_user(db: Session, user: User) -> None:
    """Replace all PII with anonymized placeholders.

    Structural data (roles, timestamps, course enrollments) is preserved
    so analytics and orphan records remain valid.
    """
    anon_id = f"deleted-{user.id}"
    user.email = f"{anon_id}@anonymized.local"
    user.username = None
    user.full_name = f"Deleted User {user.id}"
    user.hashed_password = "!DELETED"
    user.google_id = None
    user.google_access_token = None
    user.google_refresh_token = None
    user.google_granted_scopes = None
    user.is_active = False
    user.is_deleted = True
    user.email_notifications = False

    # Anonymize related student profile if exists
    from app.models.student import Student

    student = db.query(Student).filter(Student.user_id == user.id).first()
    if student:
        student.name = f"Deleted Student {user.id}"
        student.parent_email = None
        student.phone = None
        student.address = None
        student.city = None
        student.province = None
        student.postal_code = None
        student.notes = None
        student.date_of_birth = None

    # Anonymize related teacher profile if exists
    from app.models.teacher import Teacher

    teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
    if teacher:
        teacher.name = f"Deleted Teacher {user.id}"
        teacher.email = f"{anon_id}@anonymized.local"

    db.commit()
    logger.info("User %s has been anonymized", user.id)


def process_expired_deletions(db: Session) -> int:
    """Find and anonymize all users past the grace period.

    Returns the number of users anonymized.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=DELETION_GRACE_PERIOD_DAYS)
    users = (
        db.query(User)
        .filter(
            User.deletion_confirmed_at.isnot(None),
            User.deletion_confirmed_at <= cutoff,
            User.is_deleted == False,  # noqa: E712
        )
        .all()
    )

    count = 0
    for user in users:
        try:
            anonymize_user(db, user)
            count += 1
        except Exception:
            logger.exception("Failed to anonymize user %s", user.id)
            db.rollback()

    logger.info("Processed %d expired deletion(s)", count)
    return count
