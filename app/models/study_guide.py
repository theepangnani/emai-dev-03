from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, DateTime, Text, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class StudyGuide(Base):
    __tablename__ = "study_guides"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Optional references to source content
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)
    course_content_id = Column(Integer, ForeignKey("course_contents.id", ondelete="SET NULL"), nullable=True, index=True)

    # Content
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)  # Markdown or JSON content
    guide_type = Column(String(50), nullable=False, index=True)  # study_guide, quiz, flashcards
    focus_prompt = Column(String(2000), nullable=True)  # User-provided focus area saved for history
    is_truncated = Column(Boolean, default=False, nullable=False)

    # Versioning
    version = Column(Integer, nullable=False, default=1)
    parent_guide_id = Column(Integer, ForeignKey("study_guides.id", ondelete="SET NULL"), nullable=True, index=True)
    content_hash = Column(String(64), nullable=True)  # SHA-256 for duplicate detection
    relationship_type = Column(String(20), nullable=False, default="version", server_default="version")  # "version" or "sub_guide"
    generation_context = Column(Text, nullable=True)  # Selected text that triggered sub-guide generation

    # Study Guide Strategy Pattern (§6.105, #1972)
    parent_summary = Column(Text, nullable=True)  # Parent-facing simplified summary
    curriculum_codes = Column(Text, nullable=True)  # JSON array of {concept, curriculum_code, strand}
    suggestion_topics = Column(Text, nullable=True)  # JSON array of {label, description}

    # Weak area analysis (#2958)
    weak_topics = Column(Text, nullable=True)  # JSON array of weak topic strings
    ai_engine = Column(String(50), nullable=True)  # AI model used (e.g. 'claude_sonnet')

    # Sharing (parent → child)
    shared_with_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    shared_at = Column(DateTime(timezone=True), nullable=True)
    viewed_at = Column(DateTime(timezone=True), nullable=True)
    viewed_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref=backref("study_guides", passive_deletes=True))
    shared_with_user = relationship("User", foreign_keys=[shared_with_user_id])
    assignment = relationship("Assignment", backref="study_guides")
    course = relationship("Course", backref="study_guides")
    course_content = relationship("CourseContent", backref="study_guides")
    parent_guide = relationship("StudyGuide", remote_side=[id], backref="child_versions", passive_deletes=True)

    __table_args__ = (
        Index("ix_study_guides_user", "user_id"),
        Index("ix_study_guides_course_content", "course_content_id"),
    )
