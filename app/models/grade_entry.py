from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


def _letter_grade(percentage: float | None) -> str | None:
    """Convert a percentage to a letter grade using Ontario scale."""
    if percentage is None:
        return None
    if percentage >= 90:
        return "A+"
    elif percentage >= 85:
        return "A"
    elif percentage >= 80:
        return "A-"
    elif percentage >= 77:
        return "B+"
    elif percentage >= 73:
        return "B"
    elif percentage >= 70:
        return "B-"
    elif percentage >= 67:
        return "C+"
    elif percentage >= 63:
        return "C"
    elif percentage >= 60:
        return "C-"
    elif percentage >= 50:
        return "D"
    return "F"


class GradeEntry(Base):
    __tablename__ = "grade_entries"

    id = Column(Integer, primary_key=True)
    teacher_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=True)  # NULL = term mark
    term = Column(String(20), nullable=True)           # "Fall 2025", "Semester 1", etc.
    grade = Column(Float, nullable=True)               # 0-100 percentage
    max_grade = Column(Float, default=100.0)
    letter_grade = Column(String(5), nullable=True)    # auto-computed from grade
    feedback = Column(Text, nullable=True)
    is_published = Column(Boolean, default=False)      # only visible to student/parent if True
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    teacher = relationship("User", foreign_keys=[teacher_user_id])
    student = relationship("Student")
    course = relationship("Course")
    assignment = relationship("Assignment")

    __table_args__ = (
        UniqueConstraint("student_id", "assignment_id", "term", name="uq_grade_entry_student_assignment_term"),
        Index("ix_grade_entries_course", "course_id"),
        Index("ix_grade_entries_student", "student_id"),
        Index("ix_grade_entries_teacher", "teacher_user_id"),
    )
