import enum

from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime, Enum, ForeignKey,
    UniqueConstraint, Index, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class AttendanceRecord(Base):
    """Tracks individual student attendance per course per day."""

    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    date = Column(Date, nullable=False)
    status = Column(Enum(AttendanceStatus), nullable=False, default=AttendanceStatus.PRESENT)
    note = Column(Text, nullable=True)

    notified_parent = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("User", foreign_keys=[student_id])
    teacher = relationship("User", foreign_keys=[teacher_id])
    course = relationship("Course")

    __table_args__ = (
        UniqueConstraint("student_id", "course_id", "date", name="uq_attendance_student_course_date"),
        Index("ix_attendance_course_date", "course_id", "date"),
        Index("ix_attendance_student_date", "student_id", "date"),
        Index("ix_attendance_teacher", "teacher_id"),
    )


class AttendanceAlert(Base):
    """Records an alert sent to a parent when a student has 3+ consecutive absences."""

    __tablename__ = "attendance_alerts"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True)
    consecutive_absences = Column(Integer, nullable=False, default=3)
    alert_sent_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("User", foreign_keys=[student_id])
    parent = relationship("User", foreign_keys=[parent_id])
    course = relationship("Course", foreign_keys=[course_id])

    __table_args__ = (
        Index("ix_attendance_alerts_student", "student_id"),
        Index("ix_attendance_alerts_parent", "parent_id"),
    )
