from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class StudyGuide(Base):
    __tablename__ = "study_guides"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Optional references to source content
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    course_content_id = Column(Integer, ForeignKey("course_contents.id", ondelete="SET NULL"), nullable=True)

    # Content
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)  # Markdown or JSON content
    guide_type = Column(String(50), nullable=False)  # study_guide, quiz, flashcards
    focus_prompt = Column(String(2000), nullable=True)  # User-provided focus area saved for history

    # Versioning
    version = Column(Integer, nullable=False, default=1)
    parent_guide_id = Column(Integer, ForeignKey("study_guides.id", ondelete="SET NULL"), nullable=True)
    content_hash = Column(String(64), nullable=True)  # SHA-256 for duplicate detection

    # Repository reuse (#573) — when a guide is cloned from the shared content pool,
    # this points to the original guide that was reused (avoiding a new AI generation).
    source_guide_id = Column(Integer, ForeignKey("study_guides.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref=backref("study_guides", passive_deletes=True))
    assignment = relationship("Assignment", backref="study_guides")
    course = relationship("Course", backref="study_guides")
    course_content = relationship("CourseContent", backref="study_guides")
    parent_guide = relationship(
        "StudyGuide",
        foreign_keys=[parent_guide_id],
        remote_side=[id],
        backref="child_versions",
        passive_deletes=True,
    )
    source_guide = relationship(
        "StudyGuide",
        foreign_keys=[source_guide_id],
        remote_side=[id],
        backref="reused_copies",
    )

    __table_args__ = (
        Index("ix_study_guides_user", "user_id"),
        Index("ix_study_guides_course_content", "course_content_id"),
    )
