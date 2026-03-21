"""
XP and Streak models — XpSummary, StreakLog, HolidayDate.

Part of the Gamification / XP system (#2002, #2003).
"""
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String,
)
from sqlalchemy.sql import func

from app.db.database import Base


class XpSummary(Base):
    """Per-student XP summary with streak tracking."""
    __tablename__ = "xp_summary"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    total_xp = Column(Integer, default=0, nullable=False)
    current_streak = Column(Integer, default=0, nullable=False)
    longest_streak = Column(Integer, default=0, nullable=False)
    freeze_tokens_remaining = Column(Integer, default=1, nullable=False)
    last_streak_date = Column(Date, nullable=True)
    streak_broken_at = Column(DateTime(timezone=True), nullable=True)
    last_recovery_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class StreakLog(Base):
    """Daily streak log entry — one per student per day."""
    __tablename__ = "streak_log"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    log_date = Column(Date, nullable=False, index=True)
    qualifying_action = Column(String(50), nullable=True)  # e.g. "study_guide", "quiz"
    is_holiday = Column(Boolean, default=False, server_default="FALSE")
    freeze_used = Column(Boolean, default=False, server_default="FALSE")
    streak_value = Column(Integer, default=0, nullable=False)  # streak at time of log
    multiplier = Column(Float, default=1.0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HolidayDate(Base):
    """School holiday/break dates — streaks are preserved on these days."""
    __tablename__ = "holiday_dates"

    id = Column(Integer, primary_key=True, index=True)
    holiday_date = Column(Date, nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
