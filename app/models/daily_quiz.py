from sqlalchemy import Column, Integer, Float, String, Text, ForeignKey, DateTime, Date, Index, UniqueConstraint
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class DailyQuiz(Base):
    __tablename__ = "daily_quizzes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quiz_date = Column(Date, nullable=False)
    quiz_data = Column(Text, nullable=False)  # JSON: list of QuizQuestion dicts
    score = Column(Integer, nullable=True)
    total_questions = Column(Integer, nullable=False, default=5)
    percentage = Column(Float, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref=backref("daily_quizzes", passive_deletes=True))

    __table_args__ = (
        UniqueConstraint("user_id", "quiz_date", name="uq_daily_quiz_user_date"),
        Index("ix_daily_quizzes_user", "user_id"),
        Index("ix_daily_quizzes_date", "quiz_date"),
    )
