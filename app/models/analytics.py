from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class GradeRecord(Base):
    """Dedicated analytics grade row — the source of truth for all analytics queries.

    Grades flow: Google Classroom → StudentAssignment → GradeRecord.
    Manual grades and seed data are written directly here.

    Key advantages over querying StudentAssignment:
    - Pre-computed percentage (no runtime division)
    - Direct course_id FK (no Assignment→Course JOIN chain)
    - Nullable assignment_id (supports course-level grades)
    - Source tracking (google_classroom, manual, seed)
    """

    __tablename__ = "grade_records"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True)

    grade = Column(Float, nullable=False)
    max_grade = Column(Float, nullable=False)
    percentage = Column(Float, nullable=False)  # pre-computed: (grade / max_grade) * 100

    source = Column(String(50), nullable=False, default="manual")  # google_classroom, manual, seed
    recorded_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student")
    course = relationship("Course")
    assignment = relationship("Assignment")

    __table_args__ = (
        Index("ix_grade_records_student_course", "student_id", "course_id"),
        Index("ix_grade_records_student_recorded", "student_id", "recorded_at"),
    )


class ProgressReport(Base):
    """Cached weekly/monthly progress report for a student.

    Stores pre-computed analytics as JSON to avoid repeated
    expensive aggregation queries.  Generated on-demand or
    via scheduled job.
    """

    __tablename__ = "progress_reports"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    report_type = Column(String(50), nullable=False)  # "weekly", "monthly"
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    data = Column(Text, nullable=False)  # JSON string (Text for SQLite compat)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("Student")

    __table_args__ = (
        Index("ix_progress_reports_student_period", "student_id", "period_start"),
        Index("ix_progress_reports_type", "report_type"),
    )
