from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class StudyGuide(Base):
    __tablename__ = "study_guides"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Optional references to source content
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    course_content_id = Column(Integer, ForeignKey("course_contents.id"), nullable=True)

    # Content
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)  # Markdown or JSON content
    guide_type = Column(String(50), nullable=False)  # study_guide, quiz, flashcards

    # Versioning
    version = Column(Integer, nullable=False, default=1)
    parent_guide_id = Column(Integer, ForeignKey("study_guides.id"), nullable=True)
    content_hash = Column(String(64), nullable=True)  # SHA-256 for duplicate detection

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="study_guides")
    assignment = relationship("Assignment", backref="study_guides")
    course = relationship("Course", backref="study_guides")
    course_content = relationship("CourseContent", backref="study_guides")
    parent_guide = relationship("StudyGuide", remote_side=[id], backref="child_versions")
