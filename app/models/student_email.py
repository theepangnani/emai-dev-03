import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class EmailType(str, enum.Enum):
    PERSONAL = "personal"
    SCHOOL = "school"


class StudentEmail(Base):
    __tablename__ = "student_emails"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    email_type = Column(Enum(EmailType), nullable=False, default=EmailType.PERSONAL)
    is_primary = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    student = relationship("Student", backref="emails")

    __table_args__ = (
        UniqueConstraint("student_id", "email", name="uq_student_emails_pair"),
        Index("ix_student_emails_student", "student_id"),
        Index("ix_student_emails_email", "email"),
    )
