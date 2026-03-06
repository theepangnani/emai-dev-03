import re

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Text, Boolean, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


def strip_html(html: str) -> str:
    """Remove HTML tags and collapse whitespace to produce plain text."""
    if not html:
        return ""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_content_id = Column(Integer, ForeignKey("course_contents.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False, default="")         # Rich HTML content
    plain_text = Column(Text, nullable=False, default="")      # HTML-stripped for search
    has_images = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", backref="notes")
    course_content = relationship("CourseContent", backref="notes")

    __table_args__ = (
        UniqueConstraint("user_id", "course_content_id", name="uq_note_user_content"),
        Index("ix_notes_user", "user_id"),
        Index("ix_notes_course_content", "course_content_id"),
    )
