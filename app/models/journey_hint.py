"""
JourneyHint model — tracks contextual hints shown to users (#2604).

Each row records a hint that was displayed, along with whether the user
engaged (clicked Learn more / Ask Bot) or dismissed it.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.sql import func

from app.db.database import Base


class JourneyHint(Base):
    __tablename__ = "journey_hints"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    hint_key = Column(String(100), nullable=False)  # e.g. "upload_first_doc", "suppress_all"
    status = Column(String(20), nullable=False, default="shown")  # shown | dismissed | engaged
    engaged = Column(Boolean, nullable=True)  # True=clicked Learn more, False=dismissed, None=pending
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_journey_hint_user_key", "user_id", "hint_key"),
        Index("ix_journey_hint_user_created", "user_id", "created_at"),
    )
