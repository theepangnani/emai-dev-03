from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class TutorBooking(Base):
    __tablename__ = "tutor_bookings"

    id = Column(Integer, primary_key=True, index=True)
    tutor_id = Column(Integer, ForeignKey("tutor_profiles.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    requested_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Session details
    subject = Column(String(255), nullable=False)
    message = Column(Text, nullable=True)
    proposed_date = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, default=60)

    # Status
    status = Column(String(20), default="pending")  # pending | accepted | declined | completed | cancelled
    tutor_response = Column(Text, nullable=True)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # Rating (post-session)
    rating = Column(Integer, nullable=True)       # 1-5
    review_text = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tutor = relationship("TutorProfile", back_populates="bookings")
    student = relationship("Student", foreign_keys=[student_id])
    requested_by = relationship("User", foreign_keys=[requested_by_user_id])

    __table_args__ = (
        Index("ix_tutor_bookings_tutor", "tutor_id"),
        Index("ix_tutor_bookings_student", "student_id"),
        Index("ix_tutor_bookings_requester", "requested_by_user_id"),
        Index("ix_tutor_bookings_status", "status"),
    )
