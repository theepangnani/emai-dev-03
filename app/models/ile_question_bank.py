"""ILE Question Bank model — pre-generated question cache (#3197)."""
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Index,
    Integer, String, Text,
)
from sqlalchemy.sql import func

from app.db.database import Base


class ILEQuestionBank(Base):
    __tablename__ = "ile_question_bank"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(100), nullable=False)
    topic = Column(String(200), nullable=False)
    grade_level = Column(Integer, nullable=False)
    blooms_tier = Column(String(15), nullable=False, default="recall")
    difficulty = Column(String(15), nullable=False, default="medium")
    question_format = Column(String(15), nullable=False, default="mcq")
    question_json = Column(Text, nullable=False)
    explanation_text = Column(Text, nullable=True)
    hint_tree_json = Column(Text, nullable=True)  # JSON array of 3 escalating hints
    quality_score = Column(Float, nullable=True)
    times_served = Column(Integer, nullable=False, default=0)
    times_correct = Column(Integer, nullable=False, default=0)
    flagged = Column(Boolean, nullable=False, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_ile_qbank_lookup",
            "subject", "topic", "grade_level", "difficulty", "question_format",
        ),
        Index("ix_ile_qbank_expires", "expires_at"),
    )
