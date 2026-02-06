from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Float, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)

    # Google Classroom integration
    google_classroom_id = Column(String(255), unique=True, nullable=True)

    due_date = Column(DateTime(timezone=True), nullable=True)
    max_points = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    course = relationship("Course", backref="assignments")

    __table_args__ = (
        Index("ix_assignments_course_due", "course_id", "due_date"),
    )


class StudentAssignment(Base):
    __tablename__ = "student_assignments"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id"), nullable=False)

    grade = Column(Float, nullable=True)
    status = Column(String(50), default="pending")  # pending, submitted, graded
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("Student")
    assignment = relationship("Assignment")

    __table_args__ = (
        Index("ix_student_assignments_student", "student_id"),
        Index("ix_student_assignments_assignment", "assignment_id"),
    )
