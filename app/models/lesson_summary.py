import enum

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class InputType(str, enum.Enum):
    TEXT = "text"
    TRANSCRIPT = "transcript"
    AUDIO_TRANSCRIPT = "audio_transcript"
    UPLOADED_NOTES = "uploaded_notes"


class LessonSummary(Base):
    __tablename__ = "lesson_summaries"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)

    # Content fields
    title = Column(String(255), nullable=False)
    input_type = Column(Enum(InputType), nullable=False, default=InputType.TEXT)
    raw_input = Column(Text, nullable=False)

    # AI-generated structured output
    summary = Column(Text, nullable=True)
    key_concepts = Column(JSON, nullable=True)       # list of {concept: str, definition: str}
    important_dates = Column(JSON, nullable=True)    # list of {date: str, event: str}
    study_questions = Column(JSON, nullable=True)    # list of str
    action_items = Column(JSON, nullable=True)       # list of str

    # Metadata
    word_count = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    student = relationship("User", backref="lesson_summaries", foreign_keys=[student_id])
    course = relationship("Course", backref="lesson_summaries")

    __table_args__ = (
        Index("ix_lesson_summaries_student", "student_id"),
        Index("ix_lesson_summaries_course", "course_id"),
    )
