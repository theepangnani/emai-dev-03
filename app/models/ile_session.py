"""ILE Session model — tracks Flash Tutor sessions (#3197)."""
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index,
    Integer, String, Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ILESession(Base):
    __tablename__ = "ile_sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    parent_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    mode = Column(String(20), nullable=False)  # learning, testing, parent_teaching
    subject = Column(String(100), nullable=False)
    topic = Column(String(200), nullable=False)
    grade_level = Column(Integer, nullable=True)
    question_count = Column(Integer, nullable=False, default=5)
    difficulty = Column(String(15), nullable=False, default="medium")
    blooms_tier = Column(String(15), nullable=False, default="recall")
    timer_enabled = Column(Boolean, nullable=False, default=False)
    timer_seconds = Column(Integer, nullable=True)
    is_private_practice = Column(Boolean, nullable=False, default=False)
    status = Column(String(15), nullable=False, default="in_progress")
    current_question_index = Column(Integer, nullable=False, default=0)
    questions_json = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    total_correct = Column(Integer, nullable=True)
    xp_awarded = Column(Integer, nullable=True)
    streak_at_start = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    course_id = Column(
        Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )
    course_content_id = Column(
        Integer, ForeignKey("course_contents.id", ondelete="SET NULL"), nullable=True
    )
    ai_cost_estimate = Column(Float, nullable=True)
    flagged_reason = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    student = relationship("User", foreign_keys=[student_id])
    parent = relationship("User", foreign_keys=[parent_id])
    course = relationship("Course", foreign_keys=[course_id])
    course_content = relationship("CourseContent", foreign_keys=[course_content_id])
    attempts = relationship(
        "ILEQuestionAttempt", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_ile_sessions_student_status", "student_id", "status"),
        Index("ix_ile_sessions_student_topic", "student_id", "topic", "created_at"),
        Index("ix_ile_sessions_parent_status", "parent_id", "status"),
    )
