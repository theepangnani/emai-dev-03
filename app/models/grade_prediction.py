"""GradePrediction model — AI-powered grade trajectory prediction."""
from sqlalchemy import Column, Integer, Float, String, ForeignKey, Date, DateTime, JSON, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class GradePrediction(Base):
    __tablename__ = "grade_predictions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)

    predicted_grade = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False, default=0.5)  # 0.0 – 1.0
    trend = Column(String(20), nullable=False, default="stable")  # improving / stable / declining

    # List of human-readable reasoning strings from GPT-4o-mini
    factors = Column(JSON, nullable=True)  # e.g. ["Quiz average of 82% is strong", ...]

    prediction_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("User", foreign_keys=[student_id])
    course = relationship("Course", foreign_keys=[course_id])

    __table_args__ = (
        UniqueConstraint("student_id", "course_id", "prediction_date", name="uq_grade_prediction_student_course_date"),
        Index("ix_grade_predictions_student", "student_id"),
        Index("ix_grade_predictions_course", "course_id"),
    )
