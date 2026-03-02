from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Date, Float, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class QuizAssignment(Base):
    __tablename__ = "quiz_assignments"

    id = Column(Integer, primary_key=True)
    parent_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    study_guide_id = Column(Integer, ForeignKey("study_guides.id"), nullable=False)  # must be quiz type
    difficulty = Column(String(20), nullable=False, default="medium")  # easy, medium, hard
    due_date = Column(Date, nullable=True)
    assigned_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    score = Column(Float, nullable=True)          # percentage 0-100 when completed
    attempt_count = Column(Integer, default=0)
    status = Column(String(20), default="assigned")  # assigned, in_progress, completed
    note = Column(Text, nullable=True)            # optional note from parent to child

    # Relationships
    parent = relationship("User", foreign_keys=[parent_user_id])
    student = relationship("Student", backref="quiz_assignments")
    study_guide = relationship("StudyGuide", backref="quiz_assignments")

    __table_args__ = (
        Index("ix_quiz_assignments_parent", "parent_user_id"),
        Index("ix_quiz_assignments_student", "student_id"),
        Index("ix_quiz_assignments_status", "status"),
    )
