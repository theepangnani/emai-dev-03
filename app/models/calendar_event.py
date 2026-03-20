from sqlalchemy import Column, Index, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.database import Base


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        UniqueConstraint("feed_id", "uid", name="uq_calendar_event_feed_uid"),
        Index("ix_calendar_events_feed_start", "feed_id", "start_date"),
    )

    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, ForeignKey("calendar_feeds.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    uid = Column(String(500), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    all_day = Column(Boolean, default=False)
    location = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    feed = relationship("CalendarFeed", back_populates="events")
    user = relationship("User", backref="calendar_events")
