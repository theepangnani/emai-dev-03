"""DailyQuiz model -- tracks per-student daily quiz generation and completion."""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Date, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class DailyQuiz(Base):
    __tablename__ = "daily_quizzes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quiz_date = Column(Date, nullable=False)  # The calendar day this quiz is for

    # The generated quiz content (JSON array of questions)
    questions_json = Column(Text, nullable=False)
    title = Column(String(255), nullable=False)

    # Source content used to generate the quiz
    course_content_id = Column(Integer, ForeignKey("course_contents.id", ondelete="SET NULL"), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)

    # Completion tracking
    score = Column(Integer, nullable=True)  # Number of correct answers (null = not completed)
    total_questions = Column(Integer, nullable=False, default=5)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    xp_awarded = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    course_content = relationship("CourseContent", foreign_keys=[course_content_id])
    course = relationship("Course", foreign_keys=[course_id])

    __table_args__ = (
        Index("ix_daily_quizzes_user_date", "user_id", "quiz_date", unique=True),
    )
