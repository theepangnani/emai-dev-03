"""
XP Gamification models — XpLedger, XpSummary, Badge, StreakLog.

Part of the Gamification System (#2000).
"""
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String,
    UniqueConstraint, text,
)
from sqlalchemy.sql import func

from app.db.database import Base


class XpLedger(Base):
    """Append-only XP event log. Never update or delete rows."""
    __tablename__ = "xp_ledger"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type = Column(String(30), nullable=False)
    xp_awarded = Column(Integer, nullable=False)
    multiplier = Column(Float, nullable=False, default=1.0)
    awarder_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    context_id = Column(String(100), nullable=True)  # e.g. study_guide_id for quiz dedup
    reason = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class XpSummary(Base):
    """Materialized view — updated on each ledger insert."""
    __tablename__ = "xp_summary"

    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    total_xp = Column(Integer, nullable=False, default=0)
    current_level = Column(Integer, nullable=False, default=1)
    current_streak = Column(Integer, nullable=False, default=0)
    longest_streak = Column(Integer, nullable=False, default=0)
    freeze_tokens_remaining = Column(Integer, nullable=False, default=1)
    last_qualifying_action_date = Column(Date, nullable=True)
    last_streak_date = Column(Date, nullable=True)
    streak_broken_at = Column(DateTime(timezone=True), nullable=True)
    last_recovery_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Badge(Base):
    """Student badge awards."""
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    badge_id = Column(String(30), nullable=False)
    awarded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("student_id", "badge_id", name="uq_student_badge"),
    )


class StreakLog(Base):
    """Daily streak tracking."""
    __tablename__ = "streak_log"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    log_date = Column(Date, nullable=False)
    qualifying_action = Column(String(30), nullable=True)
    freeze_used = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    is_holiday = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    streak_value = Column(Integer, nullable=True)
    multiplier = Column(Float, nullable=True)

    # CB-DCI-001 M0-8 (#4183): widened to include ``qualifying_action`` so the
    # study stream and the DCI ``daily_checkin`` stream can coexist on the
    # same kid + same day. Original ``uq_student_log_date`` (student_id,
    # log_date) blocked the second stream's INSERT with IntegrityError.
    __table_args__ = (
        UniqueConstraint(
            "student_id", "log_date", "qualifying_action",
            name="uq_student_log_date_action",
        ),
    )
