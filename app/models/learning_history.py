"""
Learning History model for ASGF and Flash Tutor sessions (#3391).
"""
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.db.database import Base


class LearningHistory(Base):
    __tablename__ = "learning_history"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(
        Integer,
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id = Column(String(36), unique=True, nullable=False, index=True)
    session_type = Column(String(20), nullable=False)  # 'asgf', 'flash_tutor', 'parent_teaching'
    question_asked = Column(Text, nullable=True)
    subject = Column(String(100), nullable=True)
    topic_tags = Column(JSON, nullable=True)
    grade_level = Column(String(20), nullable=True)
    school_board = Column(String(100), nullable=True)
    documents_uploaded = Column(JSON, nullable=True)
    quiz_results = Column(JSON, nullable=True)
    overall_score_pct = Column(Integer, nullable=True)
    avg_attempts_per_q = Column(Float, nullable=True)
    weak_concepts = Column(JSON, nullable=True)
    slides_generated = Column(JSON, nullable=True)
    material_id = Column(
        Integer,
        ForeignKey("study_guides.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_to_course = Column(String(255), nullable=True)
    session_duration_sec = Column(Integer, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    teacher_visible = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="FALSE",
    )
