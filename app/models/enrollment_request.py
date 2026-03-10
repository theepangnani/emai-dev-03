from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class EnrollmentRequest(Base):
    __tablename__ = "enrollment_requests"

    id = Column(Integer, primary_key=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    requested_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # pending, approved, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    course = relationship("Course", backref="enrollment_requests")
    student = relationship("Student")
    requested_by = relationship("User", foreign_keys=[requested_by_user_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])

    __table_args__ = (
        Index("ix_enrollment_requests_course", "course_id"),
        Index("ix_enrollment_requests_student", "student_id"),
        Index("ix_enrollment_requests_status", "status"),
    )
