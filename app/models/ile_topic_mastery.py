"""ILE Topic Mastery model — per-student per-topic adaptive tracking (#3197)."""
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index,
    Integer, String,
)
from sqlalchemy.sql import func

from app.db.database import Base


class ILETopicMastery(Base):
    __tablename__ = "ile_topic_mastery"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject = Column(String(100), nullable=False)
    topic = Column(String(200), nullable=False)
    grade_level = Column(Integer, nullable=True)
    total_sessions = Column(Integer, nullable=False, default=0)
    total_questions_seen = Column(Integer, nullable=False, default=0)
    total_first_attempt_correct = Column(Integer, nullable=False, default=0)
    avg_attempts_per_question = Column(Float, nullable=False, default=0.0)
    mcq_correct_streak = Column(Integer, nullable=False, default=0)
    current_difficulty = Column(String(15), nullable=False, default="medium")
    is_weak_area = Column(Boolean, nullable=False, default=False)
    last_session_at = Column(DateTime(timezone=True), nullable=True)
    last_score_pct = Column(Float, nullable=True)
    # SM-2 spaced repetition fields
    easiness_factor = Column(Float, nullable=False, default=2.5)
    next_review_at = Column(DateTime(timezone=True), nullable=True)
    review_interval_days = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index(
            "ix_ile_mastery_student_subject_topic",
            "student_id", "subject", "topic",
            unique=True,
        ),
        Index("ix_ile_mastery_student_weak", "student_id", "is_weak_area"),
        Index("ix_ile_mastery_student_review", "student_id", "next_review_at"),
    )
