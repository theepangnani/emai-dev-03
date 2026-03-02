"""
Learning Journal models — per-course personal journal for students with AI reflection prompts
and mood tracking.
"""
import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class JournalMood(str, enum.Enum):
    excited = "excited"
    confident = "confident"
    curious = "curious"
    confused = "confused"
    frustrated = "frustrated"
    bored = "bored"


class JournalEntry(Base):
    """A personal learning journal entry written by a student."""

    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    mood = Column(Enum(JournalMood), nullable=True)
    tags = Column(JSON, nullable=True)  # list of str

    # Which AI/random prompt (if any) was used to inspire this entry
    ai_prompt_used = Column(Text, nullable=True)

    # Whether the student shared this entry with their teacher
    is_teacher_visible = Column(Boolean, nullable=False, default=False)

    # Derived at creation/update time
    word_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    student = relationship("User", foreign_keys=[student_id], lazy="select")
    course = relationship("Course", foreign_keys=[course_id], lazy="select")


class JournalReflectionPrompt(Base):
    """Pre-seeded (and AI-generated) reflection prompts shown to students."""

    __tablename__ = "journal_reflection_prompts"

    id = Column(Integer, primary_key=True, index=True)
    prompt_text = Column(Text, nullable=False)
    category = Column(String(50), nullable=False)  # weekly_review / concept_check / goal_check / emotion_check
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
