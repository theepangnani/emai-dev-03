"""Personalization models for Advanced AI Personalization (Phase 3).

Three tables:
- PersonalizationProfile: per-student learning preferences + AI-detected style
- SubjectMastery: computed mastery scores per subject/course
- AdaptiveDifficulty: track correct/incorrect streaks to adjust content difficulty
"""
import enum

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class LearningStyle(str, enum.Enum):
    VISUAL = "visual"           # prefers diagrams, charts, visual examples
    AUDITORY = "auditory"       # prefers explanations, verbal reasoning
    READING = "reading"         # prefers text, detailed notes
    KINESTHETIC = "kinesthetic" # prefers practice, hands-on, examples


class PersonalizationProfile(Base):
    """One profile per student — stores AI-detected learning style and study preferences."""

    __tablename__ = "personalization_profiles"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # AI-detected learning style
    learning_style = Column(String(20), nullable=True)           # LearningStyle enum value
    learning_style_confidence = Column(Float, default=0.0)       # 0-1 AI confidence score

    # Student preferences (editable)
    preferred_difficulty = Column(String(20), default="medium")  # "easy", "medium", "hard", "adaptive"
    study_session_length = Column(Integer, default=25)           # preferred minutes per session
    preferred_study_time = Column(String(20), default="evening") # "morning", "afternoon", "evening"

    # Subject summaries (JSON lists of subject codes)
    strong_subjects = Column(Text, default="[]")
    weak_subjects = Column(Text, default="[]")

    # AI recommendations cache (JSON)
    recommendations_json = Column(Text, nullable=True)           # latest AI recommendation payload
    recommendations_generated_at = Column(DateTime(timezone=True), nullable=True)

    last_analyzed_at = Column(DateTime(timezone=True), nullable=True)
    ai_analysis_count = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("Student", backref="personalization_profile", uselist=False)

    __table_args__ = (
        Index("ix_personalization_profiles_student", "student_id"),
    )


class SubjectMastery(Base):
    """Computed mastery score for a student in a specific subject or topic."""

    __tablename__ = "subject_mastery"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )

    subject_code = Column(String(100), nullable=False)  # Ontario course code or topic name
    subject_name = Column(String(255), nullable=False)

    # Composite mastery score
    mastery_score = Column(Float, default=0.0)          # 0-100
    mastery_level = Column(String(20), default="beginner")  # "beginner", "developing", "proficient", "advanced"

    # Component scores
    quiz_score_avg = Column(Float, default=0.0)         # average quiz percentage for this subject
    quiz_attempts = Column(Integer, default=0)          # total quiz attempts
    grade_avg = Column(Float, default=0.0)              # average grade from teacher grades / report cards

    last_quiz_date = Column(DateTime(timezone=True), nullable=True)
    trend = Column(String(20), default="stable")        # "improving", "stable", "declining"

    recommended_next_topics = Column(Text, default="[]")  # JSON list of topic strings

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    student = relationship("Student", backref="subject_masteries")

    __table_args__ = (
        UniqueConstraint("student_id", "subject_code", name="uq_subject_mastery_student_subject"),
        Index("ix_subject_mastery_student", "student_id"),
    )


class AdaptiveDifficulty(Base):
    """Track consecutive correct/incorrect attempts per student/subject/content_type.

    Used to automatically raise or lower difficulty after repeated success or failure.
    """

    __tablename__ = "adaptive_difficulty"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )

    content_type = Column(String(50), nullable=False)   # "study_guide", "quiz", "flashcard"
    subject_code = Column(String(100), nullable=False)

    current_difficulty = Column(String(20), default="medium")  # "easy", "medium", "hard"
    consecutive_correct = Column(Integer, default=0)
    consecutive_incorrect = Column(Integer, default=0)
    total_attempts = Column(Integer, default=0)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    student = relationship("Student", backref="adaptive_difficulties")

    __table_args__ = (
        UniqueConstraint(
            "student_id", "content_type", "subject_code",
            name="uq_adaptive_difficulty_student_type_subject",
        ),
        Index("ix_adaptive_difficulty_student", "student_id"),
    )
