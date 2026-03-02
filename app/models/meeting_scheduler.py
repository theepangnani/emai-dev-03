"""
Models for the parent-teacher meeting scheduler feature.

Provides:
  - TeacherAvailability: recurring weekly availability slots per teacher
  - MeetingBooking: individual meeting bookings between parents and teachers
"""
import enum
from datetime import time as time_type

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.sql import func

from app.db.database import Base


class MeetingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class MeetingType(str, enum.Enum):
    IN_PERSON = "in_person"
    VIDEO_CALL = "video_call"
    PHONE = "phone"


class TeacherAvailability(Base):
    """Recurring weekly availability window for a teacher.

    weekday: 0 = Monday … 6 = Sunday (ISO weekday - 1)
    """

    __tablename__ = "teacher_availabilities"

    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    weekday = Column(Integer, nullable=False)  # 0=Mon … 6=Sun
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    slot_duration_minutes = Column(Integer, nullable=False, default=30)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class MeetingBooking(Base):
    """A single parent-teacher meeting booking."""

    __tablename__ = "meeting_bookings"

    id = Column(Integer, primary_key=True, index=True)

    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True, index=True)

    # Requested meeting start time (UTC)
    proposed_at = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, nullable=False, default=30)

    meeting_type = Column(Enum(MeetingType), nullable=False, default=MeetingType.VIDEO_CALL)
    status = Column(Enum(MeetingStatus), nullable=False, default=MeetingStatus.PENDING, index=True)

    topic = Column(String(500), nullable=False)
    notes = Column(Text, nullable=True)  # parent notes on booking
    video_link = Column(String(1000), nullable=True)  # Zoom/Meet/Teams URL
    teacher_notes = Column(Text, nullable=True)  # teacher post-meeting notes

    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
