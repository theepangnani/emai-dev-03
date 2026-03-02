"""
Business logic for the parent-teacher meeting scheduler.

All time calculations are performed in UTC.  The frontend is responsible for
converting between the user's local timezone and UTC before/after API calls.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.meeting_scheduler import (
    MeetingBooking,
    MeetingStatus,
    MeetingType,
    TeacherAvailability,
)
from app.models.notification import Notification
from app.models.user import User
from app.schemas.meeting_scheduler import (
    AvailabilityCreate,
    AvailableSlot,
    MeetingBookingCreate,
    MeetingBookingResponse,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_response(booking: MeetingBooking, db: Session) -> MeetingBookingResponse:
    """Convert a MeetingBooking ORM object to MeetingBookingResponse, adding display names."""
    teacher = db.query(User).filter(User.id == booking.teacher_id).first()
    parent = db.query(User).filter(User.id == booking.parent_id).first()

    student_name: Optional[str] = None
    if booking.student_id:
        from app.models.student import Student
        student = db.query(Student).filter(Student.id == booking.student_id).first()
        if student:
            student_user = db.query(User).filter(User.id == student.user_id).first()
            student_name = student_user.full_name if student_user else None

    data = MeetingBookingResponse.model_validate(booking)
    data.teacher_name = teacher.full_name if teacher else None
    data.parent_name = parent.full_name if parent else None
    data.student_name = student_name
    return data


def _notify(user_id: int, title: str, body: str, db: Session) -> None:
    """Create an in-app notification for a user."""
    notif = Notification(
        user_id=user_id,
        title=title,
        body=body,
        is_read=False,
    )
    db.add(notif)
    # Caller is responsible for db.commit()


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------

class MeetingSchedulerService:
    """All meeting scheduler operations."""

    # ------------------------------------------------------------------ #
    # Availability management (teacher)
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_availability(
        teacher_id: int,
        slots: list[AvailabilityCreate],
        db: Session,
    ) -> list[TeacherAvailability]:
        """Replace a teacher's weekly availability with the provided list.

        Existing rows are soft-deactivated; new rows are inserted.
        This keeps historical bookings intact while allowing teachers to
        restructure their schedule.
        """
        # Deactivate all existing rows for this teacher
        db.query(TeacherAvailability).filter(
            TeacherAvailability.teacher_id == teacher_id
        ).update({"is_active": False})

        new_rows: list[TeacherAvailability] = []
        for slot in slots:
            row = TeacherAvailability(
                teacher_id=teacher_id,
                weekday=slot.weekday,
                start_time=slot.start_time,
                end_time=slot.end_time,
                slot_duration_minutes=slot.slot_duration_minutes,
                is_active=slot.is_active,
            )
            db.add(row)
            new_rows.append(row)

        db.commit()
        for row in new_rows:
            db.refresh(row)
        return new_rows

    @staticmethod
    def get_availability(teacher_id: int, db: Session) -> list[TeacherAvailability]:
        return (
            db.query(TeacherAvailability)
            .filter(
                TeacherAvailability.teacher_id == teacher_id,
                TeacherAvailability.is_active == True,  # noqa: E712
            )
            .order_by(TeacherAvailability.weekday, TeacherAvailability.start_time)
            .all()
        )

    # ------------------------------------------------------------------ #
    # Available slot computation
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_available_slots(
        teacher_id: int,
        date_from: datetime,
        date_to: datetime,
        db: Session,
    ) -> list[AvailableSlot]:
        """Return bookable slots between date_from and date_to (UTC).

        Algorithm:
          1. Load active TeacherAvailability rows for the teacher.
          2. For each calendar day in [date_from, date_to), check if it matches
             a weekday in the availability windows.
          3. Generate slots of slot_duration_minutes within the window.
          4. Exclude slots that overlap with existing PENDING/CONFIRMED bookings.
        """
        availabilities = (
            db.query(TeacherAvailability)
            .filter(
                TeacherAvailability.teacher_id == teacher_id,
                TeacherAvailability.is_active == True,  # noqa: E712
            )
            .all()
        )

        # Fetch booked (non-cancelled, non-completed) times for this teacher in range
        booked = (
            db.query(MeetingBooking)
            .filter(
                MeetingBooking.teacher_id == teacher_id,
                MeetingBooking.status.in_([MeetingStatus.PENDING, MeetingStatus.CONFIRMED]),
                MeetingBooking.proposed_at >= date_from,
                MeetingBooking.proposed_at < date_to,
            )
            .all()
        )

        # Build a set of (start, end) intervals that are already booked
        booked_intervals: list[tuple[datetime, datetime]] = [
            (
                b.proposed_at,
                b.proposed_at + timedelta(minutes=b.duration_minutes),
            )
            for b in booked
        ]

        def _overlaps(slot_start: datetime, slot_end: datetime) -> bool:
            for bs, be in booked_intervals:
                if slot_start < be and slot_end > bs:
                    return True
            return False

        slots: list[AvailableSlot] = []
        now = _utcnow()

        # Walk each day in range
        current_day = date_from.replace(hour=0, minute=0, second=0, microsecond=0)
        while current_day < date_to:
            weekday = current_day.weekday()  # 0=Mon … 6=Sun

            for avail in availabilities:
                if avail.weekday != weekday:
                    continue

                # Build slot boundaries for this day
                window_start = current_day.replace(
                    hour=avail.start_time.hour,
                    minute=avail.start_time.minute,
                    second=0,
                    microsecond=0,
                )
                window_end = current_day.replace(
                    hour=avail.end_time.hour,
                    minute=avail.end_time.minute,
                    second=0,
                    microsecond=0,
                )
                duration = avail.slot_duration_minutes

                slot_start = window_start
                while slot_start + timedelta(minutes=duration) <= window_end:
                    slot_end = slot_start + timedelta(minutes=duration)
                    # Only return future slots
                    if slot_start > now and not _overlaps(slot_start, slot_end):
                        slots.append(
                            AvailableSlot(
                                slot_start=slot_start,
                                slot_end=slot_end,
                                duration_minutes=duration,
                            )
                        )
                    slot_start = slot_end

            current_day += timedelta(days=1)

        return sorted(slots, key=lambda s: s.slot_start)

    # ------------------------------------------------------------------ #
    # Booking lifecycle
    # ------------------------------------------------------------------ #

    @staticmethod
    def book_meeting(
        parent_id: int,
        data: MeetingBookingCreate,
        db: Session,
    ) -> MeetingBookingResponse:
        """Parent requests a meeting; teacher is notified."""
        booking = MeetingBooking(
            teacher_id=data.teacher_id,
            parent_id=parent_id,
            student_id=data.student_id,
            proposed_at=data.proposed_at,
            duration_minutes=data.duration_minutes,
            meeting_type=data.meeting_type,
            status=MeetingStatus.PENDING,
            topic=data.topic,
            notes=data.notes,
        )
        db.add(booking)
        db.flush()  # get booking.id

        parent = db.query(User).filter(User.id == parent_id).first()
        parent_name = parent.full_name if parent else "A parent"
        _notify(
            data.teacher_id,
            title="New meeting request",
            body=f"{parent_name} has requested a meeting: {data.topic}",
            db=db,
        )

        db.commit()
        db.refresh(booking)
        return _to_response(booking, db)

    @staticmethod
    def confirm_meeting(
        booking_id: int,
        teacher_id: int,
        video_link: Optional[str],
        db: Session,
    ) -> MeetingBookingResponse:
        """Teacher confirms a pending booking."""
        booking = db.query(MeetingBooking).filter(
            MeetingBooking.id == booking_id,
            MeetingBooking.teacher_id == teacher_id,
        ).first()
        if not booking:
            raise ValueError("Booking not found or access denied")
        if booking.status != MeetingStatus.PENDING:
            raise ValueError("Only pending bookings can be confirmed")

        booking.status = MeetingStatus.CONFIRMED
        booking.confirmed_at = _utcnow()
        if video_link:
            booking.video_link = video_link

        teacher = db.query(User).filter(User.id == teacher_id).first()
        teacher_name = teacher.full_name if teacher else "Your teacher"
        _notify(
            booking.parent_id,
            title="Meeting confirmed",
            body=f"{teacher_name} confirmed your meeting on {booking.proposed_at.strftime('%b %d at %H:%M UTC')}.",
            db=db,
        )

        db.commit()
        db.refresh(booking)
        return _to_response(booking, db)

    @staticmethod
    def cancel_meeting(
        booking_id: int,
        user_id: int,
        reason: Optional[str],
        db: Session,
    ) -> MeetingBookingResponse:
        """Either party cancels a pending or confirmed booking."""
        booking = db.query(MeetingBooking).filter(
            MeetingBooking.id == booking_id,
        ).first()
        if not booking:
            raise ValueError("Booking not found")
        if booking.teacher_id != user_id and booking.parent_id != user_id:
            raise ValueError("Access denied")
        if booking.status in (MeetingStatus.CANCELLED, MeetingStatus.COMPLETED):
            raise ValueError("Cannot cancel a meeting that is already cancelled or completed")

        booking.status = MeetingStatus.CANCELLED
        booking.cancelled_at = _utcnow()
        booking.cancellation_reason = reason

        # Notify the other party
        other_id = booking.parent_id if user_id == booking.teacher_id else booking.teacher_id
        canceller = db.query(User).filter(User.id == user_id).first()
        canceller_name = canceller.full_name if canceller else "The other party"
        _notify(
            other_id,
            title="Meeting cancelled",
            body=f"{canceller_name} cancelled the meeting scheduled for {booking.proposed_at.strftime('%b %d at %H:%M UTC')}.",
            db=db,
        )

        db.commit()
        db.refresh(booking)
        return _to_response(booking, db)

    @staticmethod
    def complete_meeting(
        booking_id: int,
        teacher_id: int,
        teacher_notes: Optional[str],
        db: Session,
    ) -> MeetingBookingResponse:
        """Teacher marks the meeting as completed and optionally adds notes."""
        booking = db.query(MeetingBooking).filter(
            MeetingBooking.id == booking_id,
            MeetingBooking.teacher_id == teacher_id,
        ).first()
        if not booking:
            raise ValueError("Booking not found or access denied")
        if booking.status != MeetingStatus.CONFIRMED:
            raise ValueError("Only confirmed meetings can be marked as completed")

        booking.status = MeetingStatus.COMPLETED
        booking.completed_at = _utcnow()
        if teacher_notes:
            booking.teacher_notes = teacher_notes

        db.commit()
        db.refresh(booking)
        return _to_response(booking, db)

    # ------------------------------------------------------------------ #
    # Query helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_my_meetings(
        user_id: int,
        role: str,
        db: Session,
    ) -> list[MeetingBookingResponse]:
        """Return all meetings for the given user (parent or teacher)."""
        if role == "teacher":
            q = db.query(MeetingBooking).filter(MeetingBooking.teacher_id == user_id)
        else:
            q = db.query(MeetingBooking).filter(MeetingBooking.parent_id == user_id)

        bookings = q.order_by(MeetingBooking.proposed_at.desc()).all()
        return [_to_response(b, db) for b in bookings]

    @staticmethod
    def get_teacher_schedule(
        teacher_id: int,
        week_of: datetime,
        db: Session,
    ) -> list[MeetingBookingResponse]:
        """Return all bookings for a teacher for the 7-day week starting on week_of."""
        week_start = week_of.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)

        bookings = (
            db.query(MeetingBooking)
            .filter(
                MeetingBooking.teacher_id == teacher_id,
                MeetingBooking.proposed_at >= week_start,
                MeetingBooking.proposed_at < week_end,
            )
            .order_by(MeetingBooking.proposed_at)
            .all()
        )
        return [_to_response(b, db) for b in bookings]
