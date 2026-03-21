"""
On Track signal service — effort-based green/yellow/red indicator for parents.

Part of the "Is My Child On Track?" feature (#2020).
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.assignment import Assignment
from app.models.course import student_courses
from app.models.task import Task
from app.models.xp import XpSummary


class OnTrackService:
    @staticmethod
    def get_signal(db: Session, student_id: int, student_user_id: int) -> dict:
        """Return effort-based on-track signal for a student.

        Args:
            db: Database session.
            student_id: The student record id (students.id).
            student_user_id: The user id for the student (users.id).

        Returns:
            {signal: 'green'|'yellow'|'red', reason: str,
             last_activity_days: int|None, upcoming_count: int}
        """
        today = date.today()
        now = datetime.now(timezone.utc)

        # 1. Get last XP activity date
        summary = (
            db.query(XpSummary)
            .filter(XpSummary.student_id == student_user_id)
            .first()
        )

        last_activity_date = summary.last_qualifying_action_date if summary else None

        if last_activity_date is not None:
            last_activity_days = (today - last_activity_date).days
        else:
            last_activity_days = None  # No activity ever recorded

        # 2. Count upcoming assignments/tasks due in next 7 days
        seven_days = now + timedelta(days=7)

        # Assignments: linked via student_courses (student_id -> courses -> assignments)
        course_ids_q = (
            db.query(student_courses.c.course_id)
            .filter(student_courses.c.student_id == student_id)
        )
        upcoming_assignments = (
            db.query(Assignment)
            .filter(
                Assignment.course_id.in_(course_ids_q),
                Assignment.due_date.isnot(None),
                Assignment.due_date >= now,
                Assignment.due_date <= seven_days,
            )
            .count()
        )

        # Tasks: assigned to the student's user id
        upcoming_tasks = (
            db.query(Task)
            .filter(
                Task.assigned_to_user_id == student_user_id,
                Task.is_completed == False,  # noqa: E712
                Task.archived_at.is_(None),
                Task.due_date.isnot(None),
                Task.due_date >= now,
                Task.due_date <= seven_days,
            )
            .count()
        )

        upcoming_count = upcoming_assignments + upcoming_tasks

        # 3. Calculate signal
        signal, reason = OnTrackService._calculate_signal(
            last_activity_days, upcoming_count,
        )

        return {
            "signal": signal,
            "reason": reason,
            "last_activity_days": last_activity_days,
            "upcoming_count": upcoming_count,
        }

    @staticmethod
    def _calculate_signal(
        last_activity_days: int | None,
        upcoming_count: int,
    ) -> tuple[str, str]:
        """Determine signal and reason from activity gap and upcoming work."""
        # No activity ever recorded
        if last_activity_days is None:
            if upcoming_count > 0:
                return (
                    "red",
                    f"No study activity recorded yet and {upcoming_count} "
                    f"item{'s' if upcoming_count != 1 else ''} due within 7 days.",
                )
            return (
                "red",
                "No study activity recorded yet.",
            )

        # Escalation: upcoming work + 4+ days inactive -> red
        if upcoming_count > 0 and last_activity_days >= 4:
            return (
                "red",
                f"Last studied {last_activity_days} day{'s' if last_activity_days != 1 else ''} ago "
                f"with {upcoming_count} item{'s' if upcoming_count != 1 else ''} due within 7 days.",
            )

        # Base rules
        if last_activity_days <= 3:
            return (
                "green",
                f"Studied {last_activity_days} day{'s' if last_activity_days != 1 else ''} ago. Keep it up!",
            )

        if last_activity_days <= 6:
            return (
                "yellow",
                f"Last studied {last_activity_days} day{'s' if last_activity_days != 1 else ''} ago. "
                "A gentle check-in might help.",
            )

        # 7+ days
        return (
            "red",
            f"No study activity in {last_activity_days} days. "
            "Consider reaching out to encourage studying.",
        )
