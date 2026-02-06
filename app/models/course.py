from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Table, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


# Many-to-many relationship between students and courses
student_courses = Table(
    "student_courses",
    Base.metadata,
    Column("student_id", Integer, ForeignKey("students.id"), primary_key=True),
    Column("course_id", Integer, ForeignKey("courses.id"), primary_key=True),
)


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    subject = Column(String(100), nullable=True)

    # Google Classroom integration
    google_classroom_id = Column(String(255), unique=True, nullable=True)

    teacher_id = Column(Integer, ForeignKey("teachers.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    teacher = relationship("Teacher")
    students = relationship("Student", secondary=student_courses, backref="courses")

    __table_args__ = (
        Index("ix_courses_teacher", "teacher_id"),
    )
