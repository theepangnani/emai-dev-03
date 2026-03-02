"""Mock Exam models for AI-generated teacher exams (#667)."""
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date, Float,
    ForeignKey, JSON, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class MockExam(Base):
    __tablename__ = "mock_exams"

    id = Column(Integer, primary_key=True, index=True)
    teacher_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    # [{ "question": str, "options": [str,str,str,str], "correct_index": 0-3, "explanation": str }]
    questions = Column(JSON, nullable=False)
    time_limit_minutes = Column(Integer, default=60)
    total_marks = Column(Integer, nullable=False)  # len(questions) * marks_per_question
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_published = Column(Boolean, default=False)

    # Relationships
    teacher = relationship("User", foreign_keys=[teacher_user_id])
    course = relationship("Course", foreign_keys=[course_id])
    assignments = relationship("MockExamAssignment", back_populates="exam", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_mock_exams_teacher", "teacher_user_id"),
        Index("ix_mock_exams_course", "course_id"),
    )


class MockExamAssignment(Base):
    __tablename__ = "mock_exam_assignments"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("mock_exams.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    due_date = Column(Date, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # [int] student's chosen option indices (parallel to exam.questions)
    answers = Column(JSON, nullable=True)
    score = Column(Float, nullable=True)  # percentage 0-100
    time_taken_seconds = Column(Integer, nullable=True)
    status = Column(String(20), default="assigned")  # assigned | in_progress | completed

    # Relationships
    exam = relationship("MockExam", back_populates="assignments")
    student = relationship("Student", foreign_keys=[student_id])

    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_mock_exam_student"),
        Index("ix_mock_exam_assignments_exam", "exam_id"),
        Index("ix_mock_exam_assignments_student", "student_id"),
    )
