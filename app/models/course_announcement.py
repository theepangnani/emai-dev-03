from sqlalchemy import Column, Integer, String, DateTime, Text, Index, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class CourseAnnouncement(Base):
    __tablename__ = "course_announcements"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    google_announcement_id = Column(String(255), unique=True, nullable=False)
    text = Column(Text, nullable=True)
    creator_name = Column(String(255), nullable=True)
    creator_email = Column(String(255), nullable=True)
    creation_time = Column(DateTime(timezone=True), nullable=True)
    update_time = Column(DateTime(timezone=True), nullable=True)
    materials_json = Column(Text, nullable=True)  # JSON string of attached materials
    alternate_link = Column(String(1000), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("ix_course_announcements_course", "course_id"),
        Index("ix_course_announcements_creation_time", "course_id", "creation_time"),
    )
