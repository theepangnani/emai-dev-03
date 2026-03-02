"""Writing Assistance models for AI-powered essay feedback and improvement.

Tables:
  writing_assistance_sessions — stores user writing sessions with feedback
  writing_templates           — pre-built templates for common assignment types
"""
import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class WritingFeedbackType(str, enum.Enum):
    GRAMMAR = "grammar"
    CLARITY = "clarity"
    STRUCTURE = "structure"
    ARGUMENTATION = "argumentation"
    VOCABULARY = "vocabulary"
    OVERALL = "overall"


class WritingAssistanceSession(Base):
    """A single writing analysis session for a student."""

    __tablename__ = "writing_assistance_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    course_id = Column(
        Integer,
        ForeignKey("courses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title = Column(String(500), nullable=False)
    assignment_type = Column(String(50), nullable=False, default="essay")

    # The student's original submitted text
    original_text = Column(Text, nullable=False)

    # AI-generated improved version
    improved_text = Column(Text, nullable=True)

    # JSON list of feedback items:
    # [{"type": str, "message": str, "suggestion": str, "severity": str}]
    feedback = Column(JSON, nullable=True)

    overall_score = Column(Integer, nullable=True)  # 0-100
    word_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    course = relationship("Course", foreign_keys=[course_id])


class WritingTemplate(Base):
    """A pre-built writing template to help students get started."""

    __tablename__ = "writing_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=False)

    # essay | report | letter | lab
    template_type = Column(String(50), nullable=False, index=True)

    # Markdown structure guide shown to the student
    structure_outline = Column(Text, nullable=False)

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
