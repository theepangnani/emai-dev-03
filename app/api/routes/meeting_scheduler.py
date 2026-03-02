"""FastAPI router for the parent-teacher meeting scheduler."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.meeting_scheduler import TeacherAvailability
from app.models.user import User, UserRole
from app.schemas.meeting_scheduler import (
    AvailabilityCreate,
    AvailabilityResponse,
    AvailableSlotsResponse,
    CancelMeetingPayload,
    CompleteMeetingPayload,
    ConfirmMeetingPayload,
    MeetingBookingCreate,
    MeetingBookingResponse,
    TeacherScheduleResponse,
)
from app.services.meeting_scheduler import MeetingSchedulerService

router = APIRouter(prefix="/meetings", tags=["meetings"])


# ------------------------------------------------------------------ #
# Availability (teacher)
# ------------------------------------------------------------------ #

@router.get("/availability", response_model=list[AvailabilityResponse])
def get_my_availability(
    current_user: User = Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    """Return the calling teacher's active availability windows."""
    return MeetingSchedulerService.get_availability(current_user.id, db)


@router.put("/availability", response_model=list[AvailabilityResponse])
def set_my_availability(
    slots: list[AvailabilityCreate],
    current_user: User = Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    """Replace the calling teacher's weekly availability.

    Accepts a list of weekday/time windows.  All existing active windows are
    deactivated; the supplied list becomes the new schedule.
    """
    return MeetingSchedulerService.set_availability(current_user.id, slots, db)


# ------------------------------------------------------------------ #
# Available slots (any authenticated user — parent books, teacher previews)
# ------------------------------------------------------------------ #

@router.get("/slots/{teacher_id}", response_model=AvailableSlotsResponse)
def get_available_slots(
    teacher_id: int,
    date_from: datetime = Query(
        ...,
        description="Start of range (UTC ISO-8601), e.g. 2026-03-10T00:00:00Z",
    ),
    date_to: datetime = Query(
        ...,
        description="End of range (UTC ISO-8601), e.g. 2026-03-17T00:00:00Z",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return open booking slots for a teacher between date_from and date_to."""
    # Ensure the teacher exists
    teacher = db.query(User).filter(User.id == teacher_id).first()
    if not teacher or not teacher.has_role(UserRole.TEACHER):
        raise HTTPException(status_code=404, detail="Teacher not found")

    slots = MeetingSchedulerService.get_available_slots(teacher_id, date_from, date_to, db)
    return AvailableSlotsResponse(teacher_id=teacher_id, slots=slots)


# ------------------------------------------------------------------ #
# Booking (parent)
# ------------------------------------------------------------------ #

@router.post("/book", response_model=MeetingBookingResponse, status_code=status.HTTP_201_CREATED)
def book_meeting(
    payload: MeetingBookingCreate,
    current_user: User = Depends(require_role(UserRole.PARENT)),
    db: Session = Depends(get_db),
):
    """Parent books a meeting with a teacher."""
    try:
        return MeetingSchedulerService.book_meeting(current_user.id, payload, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ------------------------------------------------------------------ #
# List own meetings (teacher or parent)
# ------------------------------------------------------------------ #

@router.get("/", response_model=list[MeetingBookingResponse])
def list_my_meetings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all meetings for the calling user (upcoming and past)."""
    role = current_user.role.value if current_user.role else ""
    if role not in ("teacher", "parent"):
        raise HTTPException(
            status_code=403,
            detail="Only teachers and parents can access meetings",
        )
    return MeetingSchedulerService.get_my_meetings(current_user.id, role, db)


# ------------------------------------------------------------------ #
# Booking actions
# ------------------------------------------------------------------ #

@router.patch("/{booking_id}/confirm", response_model=MeetingBookingResponse)
def confirm_meeting(
    booking_id: int,
    payload: ConfirmMeetingPayload,
    current_user: User = Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    """Teacher confirms a pending meeting and optionally provides a video link."""
    try:
        return MeetingSchedulerService.confirm_meeting(
            booking_id, current_user.id, payload.video_link, db
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{booking_id}/cancel", response_model=MeetingBookingResponse)
def cancel_meeting(
    booking_id: int,
    payload: CancelMeetingPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Either party (teacher or parent) cancels a pending or confirmed meeting."""
    try:
        return MeetingSchedulerService.cancel_meeting(
            booking_id, current_user.id, payload.reason, db
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{booking_id}/complete", response_model=MeetingBookingResponse)
def complete_meeting(
    booking_id: int,
    payload: CompleteMeetingPayload,
    current_user: User = Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    """Teacher marks a confirmed meeting as completed and adds optional notes."""
    try:
        return MeetingSchedulerService.complete_meeting(
            booking_id, current_user.id, payload.teacher_notes, db
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ------------------------------------------------------------------ #
# Teacher week schedule
# ------------------------------------------------------------------ #

@router.get("/schedule", response_model=TeacherScheduleResponse)
def get_teacher_schedule(
    week_of: datetime = Query(
        ...,
        description="ISO-8601 datetime of the Monday of the desired week (UTC)",
    ),
    current_user: User = Depends(require_role(UserRole.TEACHER)),
    db: Session = Depends(get_db),
):
    """Return all bookings for the calling teacher for a given 7-day week."""
    bookings = MeetingSchedulerService.get_teacher_schedule(current_user.id, week_of, db)
    return TeacherScheduleResponse(
        week_of=week_of.date().isoformat(),
        bookings=bookings,
    )
