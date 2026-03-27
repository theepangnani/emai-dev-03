"""
Streak Service — manages daily study streaks with freeze tokens and school
calendar awareness (#2002).
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.xp import StreakLog, XpSummary
from app.models.holiday import HolidayDate

logger = logging.getLogger(__name__)

# Streak milestones that trigger parent notifications (#2224)
STREAK_MILESTONES = {7, 14, 30}


class StreakService:
    """Manages daily study streaks with freeze tokens and school calendar awareness."""

    # ── Tier definitions ────────────────────────────────────────────

    @staticmethod
    def get_streak_tier(streak_days: int) -> dict:
        """Returns visual tier info based on streak length."""
        if streak_days >= 60:
            return {"tier": "gold", "multiplier": 2.0, "label": "Legendary"}
        if streak_days >= 30:
            return {"tier": "red_glow", "multiplier": 1.75, "label": "On Fire"}
        if streak_days >= 14:
            return {"tier": "red", "multiplier": 1.5, "label": "Blazing"}
        if streak_days >= 7:
            return {"tier": "orange", "multiplier": 1.25, "label": "Warming Up"}
        return {"tier": "grey", "multiplier": 1.0, "label": "Getting Started"}

    # ── Core actions ────────────────────────────────────────────────

    @staticmethod
    def _get_or_create_summary(db: Session, student_id: int) -> XpSummary:
        """Get or create XpSummary for a student."""
        summary = db.query(XpSummary).filter(XpSummary.student_id == student_id).first()
        if not summary:
            summary = XpSummary(student_id=student_id, freeze_tokens_remaining=1)
            db.add(summary)
            db.flush()
        return summary

    @staticmethod
    def record_qualifying_action(db: Session, student_id: int, action_type: str) -> Optional[StreakLog]:
        """Called after an XP-earning action. Records today as a streak day if not already recorded."""
        today = date.today()

        # Check if today already has a streak_log entry for this student
        existing = (
            db.query(StreakLog)
            .filter(StreakLog.student_id == student_id, StreakLog.log_date == today)
            .first()
        )
        if existing:
            return existing  # Already recorded today

        summary = StreakService._get_or_create_summary(db, student_id)

        # Determine if streak continues or starts fresh
        if summary.last_streak_date and summary.last_streak_date >= today - timedelta(days=1):
            # Yesterday or today — streak continues
            summary.current_streak += 1
        elif summary.last_streak_date == today:
            # Already counted today (shouldn't reach here, but safety)
            pass
        else:
            # Gap > 1 day — start fresh streak
            summary.current_streak = 1

        summary.last_streak_date = today
        if summary.current_streak > summary.longest_streak:
            summary.longest_streak = summary.current_streak

        tier = StreakService.get_streak_tier(summary.current_streak)

        log_entry = StreakLog(
            student_id=student_id,
            log_date=today,
            qualifying_action=action_type,
            streak_value=summary.current_streak,
            multiplier=tier["multiplier"],
        )
        db.add(log_entry)
        db.commit()

        logger.info(
            "Streak recorded: student=%d action=%s streak=%d tier=%s",
            student_id, action_type, summary.current_streak, tier["tier"],
        )

        # Notify parents when a streak milestone is reached (#2224)
        if summary.current_streak in STREAK_MILESTONES:
            StreakService._notify_parents_of_milestone(db, student_id, summary.current_streak)

        return log_entry

    @staticmethod
    def _notify_parents_of_milestone(db: Session, student_user_id: int, streak_days: int) -> None:
        """Create a notification for each linked parent when a student hits a streak milestone."""
        from app.models.notification import Notification, NotificationType
        from app.models.student import Student, parent_students
        from app.models.user import User

        # Resolve the Student record from user_id
        student_record = db.query(Student).filter(Student.user_id == student_user_id).first()
        if not student_record:
            return

        # Get the student's display name
        student_user = db.query(User).filter(User.id == student_user_id).first()
        if not student_user:
            return
        child_name = student_user.full_name or "Your child"

        # Find all linked parents
        parent_rows = (
            db.query(parent_students.c.parent_id)
            .filter(parent_students.c.student_id == student_record.id)
            .all()
        )

        for (parent_id,) in parent_rows:
            notification = Notification(
                user_id=parent_id,
                type=NotificationType.SYSTEM,
                title="\U0001f525 Study Streak!",
                content=f"{child_name} has studied {streak_days} days in a row!",
            )
            db.add(notification)

        if parent_rows:
            db.commit()

    @staticmethod
    def evaluate_streak(db: Session, student_id: int) -> str:
        """Called nightly by cron. Checks if student maintained streak yesterday.

        Returns a status string: 'active', 'holiday', 'frozen', 'broken'.
        """
        yesterday = date.today() - timedelta(days=1)

        summary = db.query(XpSummary).filter(XpSummary.student_id == student_id).first()
        if not summary or summary.current_streak == 0:
            return "active"  # No streak to evaluate

        # Check if streak_log has an entry for yesterday
        yesterday_log = (
            db.query(StreakLog)
            .filter(StreakLog.student_id == student_id, StreakLog.log_date == yesterday)
            .first()
        )
        if yesterday_log:
            return "active"  # Streak continues

        # Check if yesterday was a holiday
        is_holiday = (
            db.query(HolidayDate)
            .filter(HolidayDate.date == yesterday)
            .first()
        )
        if is_holiday:
            # Create streak_log entry with is_holiday=True
            tier = StreakService.get_streak_tier(summary.current_streak)
            holiday_log = StreakLog(
                student_id=student_id,
                log_date=yesterday,
                is_holiday=True,
                streak_value=summary.current_streak,
                multiplier=tier["multiplier"],
            )
            db.add(holiday_log)
            summary.last_streak_date = yesterday
            db.commit()
            logger.info("Streak preserved (holiday): student=%d streak=%d", student_id, summary.current_streak)
            return "holiday"

        # Check freeze tokens
        if summary.freeze_tokens_remaining and summary.freeze_tokens_remaining > 0:
            tier = StreakService.get_streak_tier(summary.current_streak)
            freeze_log = StreakLog(
                student_id=student_id,
                log_date=yesterday,
                freeze_used=True,
                streak_value=summary.current_streak,
                multiplier=tier["multiplier"],
            )
            db.add(freeze_log)
            summary.freeze_tokens_remaining -= 1
            summary.last_streak_date = yesterday
            db.commit()
            logger.info(
                "Streak frozen: student=%d streak=%d tokens_left=%d",
                student_id, summary.current_streak, summary.freeze_tokens_remaining,
            )
            return "frozen"

        # No protection — break streak
        old_streak = summary.current_streak
        summary.current_streak = 0
        summary.streak_broken_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Streak broken: student=%d was=%d", student_id, old_streak)
        return "broken"

    @staticmethod
    def get_streak_info(db: Session, student_id: int) -> dict:
        """Returns streak data for display."""
        summary = StreakService._get_or_create_summary(db, student_id)
        tier = StreakService.get_streak_tier(summary.current_streak)

        return {
            "current_streak": summary.current_streak,
            "longest_streak": summary.longest_streak,
            "freeze_tokens_remaining": summary.freeze_tokens_remaining,
            "streak_tier": tier["tier"],
            "multiplier": tier["multiplier"],
            "tier_label": tier["label"],
            "last_streak_date": str(summary.last_streak_date) if summary.last_streak_date else None,
        }

    @staticmethod
    def refresh_monthly_freeze_tokens(db: Session) -> int:
        """Called on 1st of each month. Reset freeze tokens to 1 for all students."""
        count = db.query(XpSummary).update({"freeze_tokens_remaining": 1})
        db.commit()
        logger.info("Monthly freeze token refresh: updated %d students", count)
        return count

    @staticmethod
    def check_streak_recovery(db: Session, student_id: int) -> Optional[dict]:
        """Check if student is eligible for streak recovery.

        Eligible if streak was broken in last 24 hours AND no recovery in last 30 days.
        """
        summary = db.query(XpSummary).filter(XpSummary.student_id == student_id).first()
        if not summary or not summary.streak_broken_at:
            return None

        now = datetime.now(timezone.utc)
        broken_at = summary.streak_broken_at
        if broken_at.tzinfo is None:
            broken_at = broken_at.replace(tzinfo=timezone.utc)
        broken_ago = now - broken_at
        if broken_ago > timedelta(hours=24):
            return None  # Too late

        # Check no recovery in last 30 days
        if summary.last_recovery_at:
            recovery_at = summary.last_recovery_at
            if recovery_at.tzinfo is None:
                recovery_at = recovery_at.replace(tzinfo=timezone.utc)
            since_recovery = now - recovery_at
            if since_recovery < timedelta(days=30):
                return None  # Already recovered recently

        return {
            "eligible": True,
            "broken_at": summary.streak_broken_at.isoformat(),
            "previous_streak": summary.longest_streak,
            "hours_remaining": max(0, 24 - broken_ago.total_seconds() / 3600),
        }

    @staticmethod
    def recover_streak(db: Session, student_id: int) -> Optional[dict]:
        """Attempt to recover a broken streak.

        Returns recovery result or None if not eligible.
        """
        recovery_info = StreakService.check_streak_recovery(db, student_id)
        if not recovery_info:
            return None

        summary = db.query(XpSummary).filter(XpSummary.student_id == student_id).first()
        if not summary:
            return None

        # Find the last streak value before break (from the most recent streak_log)
        last_log = (
            db.query(StreakLog)
            .filter(
                StreakLog.student_id == student_id,
                StreakLog.streak_value > 0,
            )
            .order_by(StreakLog.log_date.desc())
            .first()
        )

        restored_streak = last_log.streak_value if last_log else 1

        summary.current_streak = restored_streak
        summary.streak_broken_at = None
        summary.last_recovery_at = datetime.now(timezone.utc)
        summary.last_streak_date = date.today() - timedelta(days=1)
        db.commit()

        tier = StreakService.get_streak_tier(summary.current_streak)
        logger.info("Streak recovered: student=%d restored=%d", student_id, restored_streak)

        return {
            "recovered": True,
            "current_streak": summary.current_streak,
            "streak_tier": tier["tier"],
            "multiplier": tier["multiplier"],
        }
