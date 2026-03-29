"""Journey Hint model — stub for parallel development.

The authoritative version is created by Stream 4 (#2604).
This stub provides the minimum needed to run the API endpoints.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from app.db.database import Base


class JourneyHint(Base):
    __tablename__ = "journey_hints"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    hint_key = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="shown")  # shown | dismissed | snoozed | suppressed
    shown_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    dismissed_at = Column(DateTime, nullable=True)
    snoozed_until = Column(DateTime, nullable=True)
