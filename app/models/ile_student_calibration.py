"""ILE Student Calibration model — per-student per-topic calibration (#3197)."""
from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Index,
    Integer, String,
)
from sqlalchemy.sql import func

from app.db.database import Base


class ILEStudentCalibration(Base):
    __tablename__ = "ile_student_calibration"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject = Column(String(100), nullable=False)
    topic = Column(String(200), nullable=False)
    sessions_completed = Column(Integer, nullable=False, default=0)
    baseline_accuracy = Column(Float, nullable=True)
    recommended_difficulty = Column(String(15), nullable=True)
    recommended_blooms = Column(String(15), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index(
            "ix_ile_calibration_student_subject_topic",
            "student_id", "subject", "topic",
            unique=True,
        ),
    )
