from __future__ import annotations

from datetime import datetime, date, timedelta, timezone
from typing import Optional, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.study_timer import StudySession, StudyStreak, SessionType
from app.models.student import parent_students
from app.models.user import User
from app.schemas.study_timer import StudyStatsResponse, DayStats


class StudyTimerService:
    """Business logic for Pomodoro timer sessions, streaks, and analytics."""

    # ------------------------------------------------------------------ #
    # Session management
    # ------------------------------------------------------------------ #

    def start_session(
        self,
        user_id: int,
        session_type: SessionType,
        db: Session,
        course_id: Optional[int] = None,
    ) -> StudySession:
        """Create and persist a new study session for the given user."""
        session = StudySession(
            user_id=user_id,
            session_type=session_type,
            course_id=course_id,
            started_at=datetime.now(timezone.utc),
            completed=False,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def end_session(self, session_id: int, user_id: int, db: Session) -> StudySession:
        """End a running session, calculate its duration, and update the streak."""
        session = (
            db.query(StudySession)
            .filter(StudySession.id == session_id, StudySession.user_id == user_id)
            .first()
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Study session not found",
            )
        if session.ended_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session has already ended",
            )

        now = datetime.now(timezone.utc)
        session.ended_at = now

        # Calculate duration in minutes (round down)
        started = session.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        duration_seconds = (now - started).total_seconds()
        session.duration_minutes = max(0, int(duration_seconds // 60))

        # Mark completed only for WORK sessions that ran at least 1 minute
        if session.session_type == SessionType.WORK and session.duration_minutes >= 1:
            session.completed = True
            db.commit()
            self.update_streak(user_id, db)
        else:
            db.commit()

        db.refresh(session)
        return session

    # ------------------------------------------------------------------ #
    # Streak logic
    # ------------------------------------------------------------------ #

    def get_streak(self, user_id: int, db: Session) -> StudyStreak:
        """Return the streak record for the user, creating it if it doesn't exist."""
        streak = db.query(StudyStreak).filter(StudyStreak.user_id == user_id).first()
        if not streak:
            streak = StudyStreak(user_id=user_id)
            db.add(streak)
            db.commit()
            db.refresh(streak)
        return streak

    def update_streak(self, user_id: int, db: Session) -> StudyStreak:
        """Recalculate streak after completing a work session.

        Rules:
        - If last_session_date == today: no change (already counted).
        - If last_session_date == yesterday: increment streak.
        - Anything else: reset streak to 1.
        Always update longest_streak and total_sessions / total_focus_minutes.
        """
        streak = self.get_streak(user_id, db)
        today = date.today()

        if streak.last_session_date is None:
            streak.current_streak = 1
        elif streak.last_session_date == today:
            # Already counted today's session — only update totals
            pass
        elif streak.last_session_date == today - timedelta(days=1):
            streak.current_streak += 1
        else:
            # Gap in sessions — reset
            streak.current_streak = 1

        if streak.current_streak > streak.longest_streak:
            streak.longest_streak = streak.current_streak

        # Tally completed work sessions and focus minutes
        if streak.last_session_date != today:
            streak.last_session_date = today
            streak.total_sessions += 1

        # Add focus minutes from the latest completed session
        latest = (
            db.query(StudySession)
            .filter(
                StudySession.user_id == user_id,
                StudySession.session_type == SessionType.WORK,
                StudySession.completed.is_(True),
            )
            .order_by(StudySession.ended_at.desc())
            .first()
        )
        if latest and latest.duration_minutes:
            streak.total_focus_minutes += latest.duration_minutes

        streak.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(streak)
        return streak

    # ------------------------------------------------------------------ #
    # Analytics / stats
    # ------------------------------------------------------------------ #

    def get_stats(self, user_id: int, db: Session) -> StudyStatsResponse:
        """Aggregate stats for the current user."""
        streak = self.get_streak(user_id, db)
        return self._build_stats(user_id, streak, db)

    def get_parent_child_stats(
        self, parent_id: int, student_user_id: int, db: Session
    ) -> StudyStatsResponse:
        """Return a child's stats — verifies the parent-child relationship first."""
        # Verify relationship: parent_id must have student_user_id as a linked child
        link = (
            db.execute(
                parent_students.select().where(
                    parent_students.c.parent_id == parent_id
                )
            ).fetchall()
        )
        # Resolve linked student user IDs
        from app.models.student import Student  # local import to avoid circular
        student_user_ids = []
        for row in link:
            student = db.query(Student).filter(Student.id == row.student_id).first()
            if student:
                student_user_ids.append(student.user_id)

        if student_user_id not in student_user_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this student's stats",
            )

        streak = self.get_streak(student_user_id, db)
        return self._build_stats(student_user_id, streak, db)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _build_stats(
        self, user_id: int, streak: StudyStreak, db: Session
    ) -> StudyStatsResponse:
        today = date.today()
        week_ago = today - timedelta(days=6)

        # All completed work sessions in the past 7 days
        recent_sessions: List[StudySession] = (
            db.query(StudySession)
            .filter(
                StudySession.user_id == user_id,
                StudySession.session_type == SessionType.WORK,
                StudySession.completed.is_(True),
                StudySession.ended_at.isnot(None),
            )
            .order_by(StudySession.ended_at.desc())
            .limit(200)  # Safety cap
            .all()
        )

        # Aggregate per-day
        day_map: dict[str, int] = {}
        today_minutes = 0
        week_minutes = 0

        for s in recent_sessions:
            if s.ended_at is None or s.duration_minutes is None:
                continue
            ended = s.ended_at
            if ended.tzinfo is None:
                ended = ended.replace(tzinfo=timezone.utc)
            s_date = ended.astimezone(timezone.utc).date()
            s_date_str = s_date.isoformat()

            day_map[s_date_str] = day_map.get(s_date_str, 0) + (s.duration_minutes or 0)

            if s_date == today:
                today_minutes += s.duration_minutes or 0
            if s_date >= week_ago:
                week_minutes += s.duration_minutes or 0

        # Build 7-day list (including days with 0 minutes)
        sessions_by_day: List[DayStats] = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            sessions_by_day.append(
                DayStats(date=d.isoformat(), minutes=day_map.get(d.isoformat(), 0))
            )

        return StudyStatsResponse(
            today_minutes=today_minutes,
            week_minutes=week_minutes,
            total_sessions=streak.total_sessions,
            current_streak=streak.current_streak,
            longest_streak=streak.longest_streak,
            sessions_by_day=sessions_by_day,
        )
