"""CheckinStreakSummary — per-kid streak aggregate for the DCI daily check-in
ritual (CB-DCI-001 §10).

Separate stream from the study streak (`xp_summary.current_streak`). A kid who
studies via Tutor every day but never does a check-in must NOT have a "DCI
streak" — and vice versa.

TODO: remove this file when CB-DCI-001 M0-2 (issue #4140) lands the canonical
DCI data model. Until then this stripe (M0-8) defines it locally so the streak
service can be implemented and integrated independently.
"""
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer
from sqlalchemy.sql import func

from app.db.database import Base


class CheckinStreakSummary(Base):
    """Per-kid daily check-in streak aggregate."""

    __tablename__ = "checkin_streak_summary"

    kid_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_streak = Column(Integer, nullable=False, default=0)
    longest_streak = Column(Integer, nullable=False, default=0)
    last_checkin_date = Column(Date, nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
