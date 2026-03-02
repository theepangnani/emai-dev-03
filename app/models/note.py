from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(300), nullable=True)
    content = Column(Text, nullable=False)        # Markdown supported
    color = Column(String(20), default="yellow")  # yellow, blue, green, pink, purple
    is_pinned = Column(Boolean, default=False)

    # Optional links
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    study_guide_id = Column(Integer, ForeignKey("study_guides.id", ondelete="SET NULL"), nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_archived = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", backref=backref("notes", passive_deletes=True))
    course = relationship("Course", foreign_keys=[course_id])
    study_guide = relationship("StudyGuide", foreign_keys=[study_guide_id])
    task = relationship("Task", foreign_keys=[task_id])

    __table_args__ = (
        Index("ix_notes_user_archived", "user_id", "is_archived"),
        Index("ix_notes_user_pinned", "user_id", "is_pinned"),
    )
