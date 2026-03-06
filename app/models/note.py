from sqlalchemy import Column, Integer, Text, Boolean, ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_content_id = Column(Integer, ForeignKey("course_contents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False, default="")  # Rich-text HTML
    plain_text = Column(Text, nullable=False, default="")  # Plain text for search
    has_images = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref=backref("notes", passive_deletes=True))
    course_content = relationship("CourseContent", backref=backref("notes", passive_deletes=True))

    __table_args__ = (
        UniqueConstraint("user_id", "course_content_id", name="uq_notes_user_content"),
        Index("ix_notes_user", "user_id"),
        Index("ix_notes_course_content", "course_content_id"),
    )
