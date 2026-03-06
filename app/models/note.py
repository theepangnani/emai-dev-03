from sqlalchemy import Boolean, Column, Integer, ForeignKey, DateTime, Text, Index, UniqueConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_content_id = Column(Integer, ForeignKey("course_contents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)  # HTML content
    plain_text = Column(Text, nullable=True)  # Stripped plain text for search
    has_images = Column(Boolean, nullable=False, default=False)
    highlights_json = Column(Text, nullable=True)  # JSON array: [{"text": "...", "start": 0, "end": 10}]
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref=backref("notes", passive_deletes=True))
    course_content = relationship("CourseContent", backref=backref("notes", passive_deletes=True))

    __table_args__ = (
        UniqueConstraint("user_id", "course_content_id", name="uq_notes_user_content"),
        Index("ix_notes_user_content", "user_id", "course_content_id"),
        Index("ix_notes_course_content", "course_content_id"),
        Index("ix_notes_user_updated", "user_id", "updated_at"),
    )
