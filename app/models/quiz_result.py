from sqlalchemy import Column, Integer, Float, String, Text, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func

from app.db.database import Base


class QuizResult(Base):
    __tablename__ = "quiz_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    study_guide_id = Column(Integer, ForeignKey("study_guides.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, nullable=False)
    total_questions = Column(Integer, nullable=False)
    percentage = Column(Float, nullable=False)
    answers_json = Column(Text, nullable=False)  # JSON: {"0":"A","1":"C",...}
    attempt_number = Column(Integer, nullable=False, default=1)
    time_taken_seconds = Column(Integer, nullable=True)
    completed_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref=backref("quiz_results", passive_deletes=True))
    study_guide = relationship("StudyGuide", backref=backref("quiz_results", passive_deletes=True))

    __table_args__ = (
        Index("ix_quiz_results_user", "user_id"),
        Index("ix_quiz_results_study_guide", "study_guide_id"),
        Index("ix_quiz_results_user_guide", "user_id", "study_guide_id"),
    )
