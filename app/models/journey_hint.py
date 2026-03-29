from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.sql import func

from app.db.database import Base


class JourneyHint(Base):
    __tablename__ = "journey_hints"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    hint_key = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, server_default="shown")
    shown_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)
    snooze_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "hint_key", name="uq_journey_hint_user_key"),
        Index("ix_journey_hints_user_id", "user_id"),
    )
