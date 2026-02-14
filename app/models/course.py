from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Table, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


# Many-to-many relationship between students and courses
student_courses = Table(
    "student_courses",
    Base.metadata,
    Column("student_id", Integer, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
    Column("course_id", Integer, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
)


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    subject = Column(String(100), nullable=True)

    # Google Classroom integration
    google_classroom_id = Column(String(255), unique=True, nullable=True)

    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="SET NULL"), nullable=True)

    # Parent-first platform: track who created the course and visibility
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_private = Column(Boolean, default=False, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    teacher = relationship("Teacher")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    students = relationship("Student", secondary=student_courses, backref="courses", passive_deletes=True)

    __table_args__ = (
        Index("ix_courses_teacher", "teacher_id"),
        Index("ix_courses_created_by", "created_by_user_id"),
    )
