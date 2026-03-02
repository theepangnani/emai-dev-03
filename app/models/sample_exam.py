"""SampleExam model for teacher-uploaded exam files with AI assessment (#577)."""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class SampleExam(Base):
    __tablename__ = "sample_exams"

    id = Column(Integer, primary_key=True, index=True)
    created_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id = Column(
        Integer, ForeignKey("courses.id", ondelete="SET NULL"), nullable=True
    )
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)

    # Content — extracted text from the uploaded file
    original_content = Column(Text, nullable=True)
    file_name = Column(String(500), nullable=True)

    # AI Assessment — JSON payload produced after upload
    assessment_json = Column(Text, nullable=True)
    assessment_generated_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    exam_type = Column(String(50), nullable=False, default="sample")
    difficulty_level = Column(String(20), nullable=True)  # easy | medium | hard
    is_public = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    course = relationship("Course", foreign_keys=[course_id])

    __table_args__ = (
        Index("ix_sample_exams_creator", "created_by_user_id"),
        Index("ix_sample_exams_course", "course_id"),
        Index("ix_sample_exams_is_public", "is_public"),
    )
