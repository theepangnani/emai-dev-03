from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.wellness import WellnessCheckIn, WellnessAlert, MoodLevel, EnergyLevel
from app.models.student import Student, parent_students
from app.models.notification import Notification, NotificationType
from app.schemas.wellness import (
    WellnessCheckInCreate,
    WellnessCheckInResponse,
    WellnessTrendResponse,
    WellnessSummary,
    DayTrendPoint,
)


# Mood levels considered "low" for alert purposes
_LOW_MOOD_LEVELS = {MoodLevel.STRUGGLING, MoodLevel.OVERWHELMED}

# Numeric scores for averaging moods (higher = better)
_MOOD_SCORE = {
    MoodLevel.GREAT: 5,
    MoodLevel.GOOD: 4,
    MoodLevel.OKAY: 3,
    MoodLevel.STRUGGLING: 2,
    MoodLevel.OVERWHELMED: 1,
}

_SCORE_TO_MOOD = {v: k for k, v in _MOOD_SCORE.items()}

_ENERGY_SCORE = {
    EnergyLevel.HIGH: 3,
    EnergyLevel.MEDIUM: 2,
    EnergyLevel.LOW: 1,
}

_SCORE_TO_ENERGY = {v: k for k, v in _ENERGY_SCORE.items()}


class WellnessService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    def create_check_in(
        self, student_id: int, data: WellnessCheckInCreate
    ) -> WellnessCheckInResponse:
        """Create or update today's wellness check-in for the student (upsert)."""
        today = date.today()

        existing = (
            self.db.query(WellnessCheckIn)
            .filter(
                WellnessCheckIn.student_id == student_id,
                WellnessCheckIn.check_in_date == today,
            )
            .first()
        )

        if existing:
            existing.mood = data.mood
            existing.energy = data.energy
            existing.stress_level = data.stress_level
            existing.sleep_hours = data.sleep_hours
            existing.notes = data.notes
            existing.is_private = data.is_private
            self.db.commit()
            self.db.refresh(existing)
            return WellnessCheckInResponse.model_validate(existing)

        check_in = WellnessCheckIn(
            student_id=student_id,
            mood=data.mood,
            energy=data.energy,
            stress_level=data.stress_level,
            sleep_hours=data.sleep_hours,
            notes=data.notes,
            is_private=data.is_private,
            check_in_date=today,
        )
        self.db.add(check_in)
        self.db.commit()
        self.db.refresh(check_in)
        return WellnessCheckInResponse.model_validate(check_in)

    def get_today(self, student_id: int) -> Optional[WellnessCheckInResponse]:
        """Return today's check-in for the student, or None if not yet submitted."""
        today = date.today()
        row = (
            self.db.query(WellnessCheckIn)
            .filter(
                WellnessCheckIn.student_id == student_id,
                WellnessCheckIn.check_in_date == today,
            )
            .first()
        )
        if not row:
            return None
        return WellnessCheckInResponse.model_validate(row)

    # ------------------------------------------------------------------
    # Trend / summary helpers
    # ------------------------------------------------------------------

    def get_trend(
        self,
        student_id: int,
        days: int = 7,
        exclude_private: bool = False,
    ) -> WellnessTrendResponse:
        """Return a per-day breakdown for the last `days` days."""
        today = date.today()
        start = today - timedelta(days=days - 1)

        query = self.db.query(WellnessCheckIn).filter(
            WellnessCheckIn.student_id == student_id,
            WellnessCheckIn.check_in_date >= start,
            WellnessCheckIn.check_in_date <= today,
        )
        if exclude_private:
            query = query.filter(WellnessCheckIn.is_private == False)  # noqa: E712

        rows = {r.check_in_date: r for r in query.all()}

        day_points: list[DayTrendPoint] = []
        streak = 0
        check_days = 0

        for i in range(days):
            d = start + timedelta(days=i)
            row = rows.get(d)
            if row:
                day_points.append(
                    DayTrendPoint(
                        date=d,
                        mood=row.mood,
                        energy=row.energy,
                        stress_level=row.stress_level,
                        sleep_hours=row.sleep_hours,
                        has_entry=True,
                    )
                )
                check_days += 1
            else:
                day_points.append(DayTrendPoint(date=d, has_entry=False))

        # Compute streak (consecutive days ending today)
        for point in reversed(day_points):
            if point.has_entry:
                streak += 1
            else:
                break

        # Aggregates
        entries = [p for p in day_points if p.has_entry]
        avg_stress: Optional[float] = None
        avg_sleep: Optional[float] = None
        dominant_mood: Optional[MoodLevel] = None
        dominant_energy: Optional[EnergyLevel] = None

        if entries:
            avg_stress = round(sum(p.stress_level for p in entries) / len(entries), 2)
            sleep_entries = [p.sleep_hours for p in entries if p.sleep_hours is not None]
            if sleep_entries:
                avg_sleep = round(sum(sleep_entries) / len(sleep_entries), 2)

            mood_counter = Counter(p.mood for p in entries if p.mood)
            if mood_counter:
                dominant_mood = mood_counter.most_common(1)[0][0]

            energy_counter = Counter(p.energy for p in entries if p.energy)
            if energy_counter:
                dominant_energy = energy_counter.most_common(1)[0][0]

        return WellnessTrendResponse(
            days=day_points,
            avg_stress=avg_stress,
            avg_sleep=avg_sleep,
            dominant_mood=dominant_mood,
            dominant_energy=dominant_energy,
            streak_days=streak,
        )

    def get_student_summary(self, student_id: int, exclude_private: bool = False) -> WellnessSummary:
        """Return a weekly summary for a student."""
        trend = self.get_trend(student_id, days=7, exclude_private=exclude_private)
        entries_this_week = sum(1 for p in trend.days if p.has_entry)

        # Check if there is an active alert (within the last 7 days)
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        alert = (
            self.db.query(WellnessAlert)
            .filter(
                WellnessAlert.student_id == student_id,
                WellnessAlert.created_at >= seven_days_ago,
            )
            .first()
        )

        return WellnessSummary(
            student_id=student_id,
            week_avg_stress=trend.avg_stress,
            week_avg_sleep=trend.avg_sleep,
            dominant_mood=trend.dominant_mood,
            dominant_energy=trend.dominant_energy,
            alert_active=alert is not None,
            total_check_ins_this_week=entries_this_week,
            streak_days=trend.streak_days,
        )

    # ------------------------------------------------------------------
    # Parent view
    # ------------------------------------------------------------------

    def get_parent_child_wellness(
        self, parent_id: int, student_id: int
    ) -> WellnessTrendResponse:
        """Verify parent-child link and return trend (excluding private entries)."""
        # Verify link: look up student record for this user_id then check parent_students
        student = (
            self.db.query(Student)
            .filter(Student.user_id == student_id)
            .first()
        )
        if not student:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
            )

        link = self.db.execute(
            select(parent_students).where(
                parent_students.c.parent_id == parent_id,
                parent_students.c.student_id == student.id,
            )
        ).first()

        if not link:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not linked to this student",
            )

        return self.get_trend(student_id, days=7, exclude_private=True)

    # ------------------------------------------------------------------
    # Alert job
    # ------------------------------------------------------------------

    def check_and_alert(self) -> int:
        """
        Scan all students with check-ins in the last 7 days.
        If >= 3 days have struggling/overwhelmed mood, create a WellnessAlert
        and send notifications to linked parents + assigned teachers.
        Returns number of alerts created.
        """
        from sqlalchemy import func as sqlfunc

        today = date.today()
        seven_days_ago = today - timedelta(days=7)

        # Find (student_id, low_mood_count) pairs
        results = (
            self.db.query(
                WellnessCheckIn.student_id,
                sqlfunc.count(WellnessCheckIn.id).label("low_count"),
            )
            .filter(
                WellnessCheckIn.check_in_date >= seven_days_ago,
                WellnessCheckIn.check_in_date <= today,
                WellnessCheckIn.mood.in_(list(_LOW_MOOD_LEVELS)),
            )
            .group_by(WellnessCheckIn.student_id)
            .having(sqlfunc.count(WellnessCheckIn.id) >= 3)
            .all()
        )

        alerts_created = 0

        for row in results:
            student_user_id: int = row.student_id
            low_count: int = row.low_count

            # Avoid duplicate alerts within the same 7-day window
            seven_days_ago_dt = datetime.now(timezone.utc) - timedelta(days=7)
            existing_alert = (
                self.db.query(WellnessAlert)
                .filter(
                    WellnessAlert.student_id == student_user_id,
                    WellnessAlert.created_at >= seven_days_ago_dt,
                )
                .first()
            )
            if existing_alert:
                continue

            # Create alert record
            triggered_by = (
                f"{low_count} struggling/overwhelmed check-ins in the last 7 days"
            )
            alert = WellnessAlert(
                student_id=student_user_id,
                triggered_by=triggered_by,
                alert_sent_at=datetime.now(timezone.utc),
            )
            self.db.add(alert)

            # Notify linked parents
            student = (
                self.db.query(Student)
                .filter(Student.user_id == student_user_id)
                .first()
            )
            if student:
                for parent_user in student.parents:
                    notif = Notification(
                        user_id=parent_user.id,
                        type=NotificationType.SYSTEM,
                        title="Wellness Alert",
                        content=(
                            f"Your child has had {low_count} days of struggling "
                            "or overwhelmed mood in the past week. "
                            "Consider checking in with them."
                        ),
                        link="/wellness",
                    )
                    self.db.add(notif)

            # Notify assigned teachers
            from app.models.student import student_teachers as st_table
            teacher_rows = self.db.execute(
                select(st_table).where(
                    st_table.c.student_id == (student.id if student else -1)
                )
            ).fetchall()

            for t_row in teacher_rows:
                if t_row.teacher_user_id:
                    notif = Notification(
                        user_id=t_row.teacher_user_id,
                        type=NotificationType.SYSTEM,
                        title="Student Wellness Alert",
                        content=(
                            f"A student has had {low_count} days of struggling "
                            "or overwhelmed mood in the past week."
                        ),
                        link=f"/wellness/student/{student_user_id}/summary" if student else "/wellness",
                    )
                    self.db.add(notif)

            self.db.commit()
            alerts_created += 1

        return alerts_created
