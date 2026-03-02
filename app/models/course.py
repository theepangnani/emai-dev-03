from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Table, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


# Valid classroom types
CLASSROOM_TYPE_SCHOOL = "school"
CLASSROOM_TYPE_PRIVATE = "private"
CLASSROOM_TYPE_MANUAL = "manual"
VALID_CLASSROOM_TYPES = {CLASSROOM_TYPE_SCHOOL, CLASSROOM_TYPE_PRIVATE, CLASSROOM_TYPE_MANUAL}


# Many-to-many relationship between students and courses
student_courses = Table(
    "student_courses",
    Base.metadata,
    Column("student_id", Integer, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
    Column("course_id", Integer, ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
    Index("ix_student_courses_student", "student_id"),
    Index("ix_student_courses_course", "course_id"),
)


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=True)
    subject = Column(String(100), nullable=True)

    # Google Classroom integration
    google_classroom_id = Column(String(255), unique=True, nullable=True)

    # Multi-LMS: generic provider tracking (#22)
    # "google_classroom" | "brightspace" | "canvas" | None
    lms_provider = Column(String(50), nullable=True)
    # External ID in the source LMS (complements google_classroom_id for other providers)
    lms_external_id = Column(String(255), nullable=True)

    classroom_type = Column(String(20), nullable=False, default="manual", server_default="manual")  # "school", "private", or "manual"

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

    @property
    def teacher_name(self) -> str | None:
        if not self.teacher:
            return None
        if self.teacher.is_shadow:
            return self.teacher.full_name
        return self.teacher.user.full_name if self.teacher.user else None

    @property
    def teacher_email(self) -> str | None:
        if not self.teacher:
            return None
        if self.teacher.is_shadow:
            return self.teacher.google_email
        return self.teacher.user.email if self.teacher.user else None

    @property
    def student_count(self) -> int:
        return len(self.students) if self.students else 0

    @property
    def is_school_course(self) -> bool:
        """Whether this is a school Google Classroom course (read-only restrictions apply)."""
        return self.classroom_type == CLASSROOM_TYPE_SCHOOL

    __table_args__ = (
        Index("ix_courses_teacher", "teacher_id"),
        Index("ix_courses_created_by", "created_by_user_id"),
    )
