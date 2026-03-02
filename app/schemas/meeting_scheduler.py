"""Pydantic schemas for the meeting scheduler feature."""
from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models.meeting_scheduler import MeetingStatus, MeetingType


# ---------------------------------------------------------------------------
# Teacher availability
# ---------------------------------------------------------------------------

class AvailabilityCreate(BaseModel):
    """Single weekly availability slot for a teacher."""
    weekday: int  # 0=Mon … 6=Sun
    start_time: time
    end_time: time
    slot_duration_minutes: int = 30
    is_active: bool = True

    @field_validator("weekday")
    @classmethod
    def validate_weekday(cls, v: int) -> int:
        if v < 0 or v > 6:
            raise ValueError("weekday must be 0 (Monday) through 6 (Sunday)")
        return v

    @field_validator("end_time")
    @classmethod
    def validate_times(cls, end: time, info) -> time:
        start = info.data.get("start_time")
        if start and end <= start:
            raise ValueError("end_time must be after start_time")
        return end

    model_config = {"from_attributes": True}


class AvailabilityResponse(AvailabilityCreate):
    id: int
    teacher_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Available slots (computed, not stored)
# ---------------------------------------------------------------------------

class AvailableSlot(BaseModel):
    """A single computed available booking slot."""
    slot_start: datetime
    slot_end: datetime
    duration_minutes: int


class AvailableSlotsResponse(BaseModel):
    teacher_id: int
    slots: list[AvailableSlot]


# ---------------------------------------------------------------------------
# Meeting booking
# ---------------------------------------------------------------------------

class MeetingBookingCreate(BaseModel):
    """Payload sent by a parent to request a meeting."""
    teacher_id: int
    student_id: Optional[int] = None
    proposed_at: datetime
    duration_minutes: int = 30
    meeting_type: MeetingType = MeetingType.VIDEO_CALL
    topic: str
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class MeetingBookingResponse(BaseModel):
    id: int
    teacher_id: int
    parent_id: int
    student_id: Optional[int] = None
    proposed_at: datetime
    duration_minutes: int
    meeting_type: MeetingType
    status: MeetingStatus
    topic: str
    notes: Optional[str] = None
    video_link: Optional[str] = None
    teacher_notes: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Resolved display names (populated by service)
    teacher_name: Optional[str] = None
    parent_name: Optional[str] = None
    student_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Action payloads
# ---------------------------------------------------------------------------

class ConfirmMeetingPayload(BaseModel):
    video_link: Optional[str] = None


class CancelMeetingPayload(BaseModel):
    reason: Optional[str] = None


class CompleteMeetingPayload(BaseModel):
    teacher_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Week schedule response
# ---------------------------------------------------------------------------

class TeacherScheduleResponse(BaseModel):
    week_of: str  # ISO date of Monday of the requested week
    bookings: list[MeetingBookingResponse]
