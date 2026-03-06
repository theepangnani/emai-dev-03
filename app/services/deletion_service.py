"""Account deletion and data anonymization service (#964).

Handles soft-delete requests, grace period management, and PII anonymization.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

GRACE_PERIOD_DAYS = 30
ANON_EMAIL_TEMPLATE = "deleted_user_{user_id}@anonymized.local"
ANON_NAME = "Deleted User"


def request_deletion(db: Session, user: User) -> User:
    """Mark a user account for deletion with a 30-day grace period."""
    user.deletion_requested_at = datetime.now(timezone.utc)
    user.deletion_confirmed = True
    db.commit()
    db.refresh(user)
    return user


def cancel_deletion(db: Session, user: User) -> User:
    """Cancel a pending deletion request during the grace period."""
    user.deletion_requested_at = None
    user.deletion_confirmed = False
    db.commit()
    db.refresh(user)
    return user


def is_deletion_pending(user: User) -> bool:
    """Check if a user has a pending deletion request."""
    return bool(user.deletion_requested_at and user.deletion_confirmed and not user.is_deleted)


def get_grace_period_end(user: User) -> datetime | None:
    """Return the datetime when the grace period ends, or None."""
    if not user.deletion_requested_at:
        return None
    # Handle both tz-aware and naive datetimes from DB
    requested = user.deletion_requested_at
    if requested.tzinfo is None:
        requested = requested.replace(tzinfo=timezone.utc)
    return requested + timedelta(days=GRACE_PERIOD_DAYS)


def anonymize_user(db: Session, user: User) -> None:
    """Anonymize all PII on a user record. Called after grace period expires."""
    user.email = ANON_EMAIL_TEMPLATE.format(user_id=user.id)
    user.username = f"deleted_{user.id}"
    user.full_name = ANON_NAME
    user.hashed_password = "DELETED"
    user.is_active = False
    user.is_deleted = True
    user.google_id = None
    user.google_access_token = None
    user.google_refresh_token = None
    user.google_granted_scopes = None

    # Anonymize related records
    _anonymize_conversations(db, user.id)
    _anonymize_messages(db, user.id)
    _anonymize_study_materials(db, user.id)

    db.commit()
    logger.info("Anonymized user %d", user.id)


def _anonymize_conversations(db: Session, user_id: int) -> None:
    """Anonymize conversations involving the deleted user."""
    from app.models.message import Conversation
    convos = db.query(Conversation).filter(
        (Conversation.participant_1_id == user_id) | (Conversation.participant_2_id == user_id)
    ).all()
    for convo in convos:
        # Don't delete — just leave them; the user name will show as "Deleted User"
        pass


def _anonymize_messages(db: Session, user_id: int) -> None:
    """Anonymize message content from the deleted user."""
    from app.models.message import Message
    messages = db.query(Message).filter(Message.sender_id == user_id).all()
    for msg in messages:
        msg.content = "[Message from deleted user]"


def _anonymize_study_materials(db: Session, user_id: int) -> None:
    """Anonymize study guides owned by the deleted user (keep content, remove ownership PII)."""
    from app.models.study_guide import StudyGuide
    guides = db.query(StudyGuide).filter(StudyGuide.user_id == user_id).all()
    for guide in guides:
        # Keep the educational content but disassociate from user
        pass  # user_id FK will point to the anonymized user record


def process_expired_deletions(db: Session) -> int:
    """Process all deletion requests that have passed the grace period.

    Returns the number of accounts processed.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=GRACE_PERIOD_DAYS)

    pending_users = db.query(User).filter(
        User.deletion_confirmed == True,
        User.is_deleted == False,
        User.deletion_requested_at.isnot(None),
        User.deletion_requested_at <= cutoff,
    ).all()

    count = 0
    for user in pending_users:
        try:
            anonymize_user(db, user)
            count += 1
        except Exception as e:
            logger.error("Failed to anonymize user %d: %s", user.id, e)
            db.rollback()

    return count


def get_pending_deletions(db: Session, skip: int = 0, limit: int = 50) -> tuple[list[User], int]:
    """Get all users with pending deletion requests (admin view)."""
    query = db.query(User).filter(
        User.deletion_confirmed == True,
        User.is_deleted == False,
        User.deletion_requested_at.isnot(None),
    )
    total = query.count()
    users = query.order_by(User.deletion_requested_at.asc()).offset(skip).limit(limit).all()
    return users, total


def admin_process_deletion(db: Session, user_id: int) -> User:
    """Admin force-processes a deletion immediately, bypassing grace period."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")
    if user.is_deleted:
        raise ValueError("User is already deleted")
    anonymize_user(db, user)
    return user
