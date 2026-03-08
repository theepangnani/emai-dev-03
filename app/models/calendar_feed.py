from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.database import Base


class CalendarFeed(Base):
    __tablename__ = "calendar_feeds"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    url = Column(String(1000), nullable=False)
    name = Column(String(255), nullable=True)
    last_synced = Column(DateTime(timezone=True), nullable=True)
    event_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="calendar_feeds")
    events = relationship("CalendarEvent", back_populates="feed", cascade="all, delete-orphan")
