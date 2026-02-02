import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.user import User
from app.models.teacher_communication import TeacherCommunication, CommunicationType
from app.models.notification import Notification, NotificationType
from app.services.gmail_monitor import fetch_teacher_emails
from app.services.classroom_monitor import fetch_classroom_announcements
from app.services.ai_service import summarize_teacher_communication

logger = logging.getLogger(__name__)


async def sync_user_communications(user_id: int, db: Session) -> dict:
    """Sync Gmail and Classroom communications for a single user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.google_access_token:
        return {"synced": 0}

    new_count = 0

    # 1. Sync Gmail
    try:
        emails, creds = fetch_teacher_emails(
            user.google_access_token,
            user.google_refresh_token,
            after_timestamp=user.gmail_last_sync,
        )

        # Update tokens if refreshed
        if creds.token != user.google_access_token:
            user.google_access_token = creds.token
            if creds.refresh_token:
                user.google_refresh_token = creds.refresh_token

        for email_data in emails:
            existing = db.query(TeacherCommunication).filter(
                TeacherCommunication.user_id == user.id,
                TeacherCommunication.source_id == email_data["source_id"],
            ).first()

            if existing:
                continue

            # Generate AI summary
            summary = None
            try:
                summary = await summarize_teacher_communication(
                    subject=email_data.get("subject", ""),
                    body=email_data.get("body", ""),
                    sender_name=email_data.get("sender_name", ""),
                    comm_type="email",
                )
            except Exception as e:
                logger.warning(f"AI summary failed for email: {e}")

            comm = TeacherCommunication(
                user_id=user.id,
                type=CommunicationType.EMAIL,
                source_id=email_data["source_id"],
                sender_name=email_data.get("sender_name"),
                sender_email=email_data.get("sender_email"),
                subject=email_data.get("subject"),
                body=email_data.get("body"),
                snippet=email_data.get("snippet"),
                ai_summary=summary,
                received_at=email_data.get("received_at"),
            )
            db.add(comm)
            new_count += 1

            notif = Notification(
                user_id=user.id,
                type=NotificationType.MESSAGE,
                title=f"Email from {email_data.get('sender_name', 'Teacher')}",
                content=email_data.get("subject", "New email"),
                link="/teacher-communications",
            )
            db.add(notif)

        user.gmail_last_sync = datetime.now(timezone.utc)

    except Exception as e:
        logger.error(f"Gmail sync failed for user {user.id}: {e}", exc_info=True)

    # 2. Sync Classroom announcements
    try:
        announcements, creds = fetch_classroom_announcements(
            user.google_access_token,
            user.google_refresh_token,
        )

        if creds.token != user.google_access_token:
            user.google_access_token = creds.token
            if creds.refresh_token:
                user.google_refresh_token = creds.refresh_token

        for ann_data in announcements:
            existing = db.query(TeacherCommunication).filter(
                TeacherCommunication.user_id == user.id,
                TeacherCommunication.source_id == ann_data["source_id"],
            ).first()

            if existing:
                continue

            summary = None
            try:
                summary = await summarize_teacher_communication(
                    subject=ann_data.get("subject", ""),
                    body=ann_data.get("body", ""),
                    sender_name=ann_data.get("sender_name", "Teacher"),
                    comm_type="announcement",
                )
            except Exception as e:
                logger.warning(f"AI summary failed for announcement: {e}")

            comm = TeacherCommunication(
                user_id=user.id,
                type=CommunicationType.ANNOUNCEMENT,
                source_id=ann_data["source_id"],
                sender_name=ann_data.get("sender_name"),
                subject=ann_data.get("subject"),
                body=ann_data.get("body"),
                snippet=ann_data.get("snippet"),
                ai_summary=summary,
                course_name=ann_data.get("course_name"),
                course_id=ann_data.get("course_id"),
                received_at=ann_data.get("received_at"),
            )
            db.add(comm)
            new_count += 1

            notif = Notification(
                user_id=user.id,
                type=NotificationType.MESSAGE,
                title=f"Announcement: {ann_data.get('course_name', 'Course')}",
                content=ann_data.get("snippet", "")[:100],
                link="/teacher-communications",
            )
            db.add(notif)

        user.classroom_last_sync = datetime.now(timezone.utc)

    except Exception as e:
        logger.error(f"Classroom sync failed for user {user.id}: {e}", exc_info=True)

    db.commit()
    return {"synced": new_count}


async def check_teacher_communications():
    """Background job: sync teacher communications for all connected users.

    Runs every 15 minutes.
    """
    logger.info("Running teacher communication sync...")

    db: Session = SessionLocal()
    try:
        users = (
            db.query(User)
            .filter(User.google_access_token.isnot(None))
            .filter(User.is_active == True)
            .all()
        )

        total_synced = 0
        for user in users:
            try:
                result = await sync_user_communications(user.id, db)
                total_synced += result.get("synced", 0)
            except Exception as e:
                logger.error(f"Sync failed for user {user.id}: {e}")

        logger.info(
            f"Teacher communication sync complete | "
            f"new_items={total_synced} | users_checked={len(users)}"
        )

    except Exception as e:
        logger.error(f"Teacher communication sync job failed: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()
