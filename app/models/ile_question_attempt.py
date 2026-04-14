"""ILE Question Attempt model — per-question attempt tracking (#3197)."""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index,
    Integer, String, Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ILEQuestionAttempt(Base):
    __tablename__ = "ile_question_attempts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer, ForeignKey("ile_sessions.id", ondelete="CASCADE"), nullable=False
    )
    question_index = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    question_format = Column(String(15), nullable=False, default="mcq")
    difficulty_level = Column(String(15), nullable=False, default="medium")
    selected_answer = Column(String(500), nullable=True)
    correct_answer = Column(String(500), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    attempt_number = Column(Integer, nullable=False, default=1)
    hint_shown = Column(Text, nullable=True)
    # COMMENTED OUT: Column not yet in production DB — migration pending. (#3300)
    # parent_hint_note = Column(Text, nullable=True)  # Parent Teaching Mode: parent's personal hint
    explanation_shown = Column(Text, nullable=True)
    time_taken_ms = Column(Integer, nullable=True)
    xp_earned = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("ILESession", back_populates="attempts")

    __table_args__ = (
        Index("ix_ile_attempts_session_qi", "session_id", "question_index"),
        Index("ix_ile_attempts_session_correct", "session_id", "is_correct"),
    )
