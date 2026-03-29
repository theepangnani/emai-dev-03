"""
Journey Hint model — tracks which hints have been shown, dismissed,
snoozed, or suppressed for each user.

NOTE: If #2604 provides an authoritative version of this model,
the integration merge should keep that one.
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.sql import func

from app.db.database import Base


class JourneyHint(Base):
    __tablename__ = "journey_hints"
    __table_args__ = (
        Index("ix_journey_hints_user", "user_id"),
        Index("ix_journey_hints_user_key", "user_id", "hint_key"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    hint_key = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="shown")  # shown, dismissed, completed, suppress_all
    shown_at = Column(DateTime(timezone=True), server_default=func.now())
    dismissed_at = Column(DateTime(timezone=True), nullable=True)
    snooze_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
