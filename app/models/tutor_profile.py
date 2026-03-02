from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class TutorProfile(Base):
    __tablename__ = "tutor_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Professional info
    bio = Column(Text, nullable=False)
    headline = Column(String(255), nullable=False)
    subjects = Column(Text, nullable=False)       # JSON list: ["Mathematics", "Physics"]
    grade_levels = Column(Text, nullable=False)   # JSON list: ["9", "10", "11", "12"]
    languages = Column(Text, default='["English"]')  # JSON list

    # Rates & availability
    hourly_rate_cad = Column(Float, nullable=False)
    session_duration_minutes = Column(Integer, default=60)
    available_days = Column(Text, default='["Monday","Tuesday","Wednesday","Thursday","Friday"]')  # JSON
    available_hours_start = Column(String(5), default="16:00")   # HH:MM
    available_hours_end = Column(String(5), default="20:00")
    timezone = Column(String(50), default="America/Toronto")
    online_only = Column(Boolean, default=False)
    location_city = Column(String(100), nullable=True)

    # Credentials
    is_verified = Column(Boolean, default=False)   # admin sets this
    years_experience = Column(Integer, nullable=True)
    certifications = Column(Text, nullable=True)   # JSON list
    school_affiliation = Column(String(255), nullable=True)

    # Stats (denormalized, updated on booking review)
    total_sessions = Column(Integer, default=0)
    avg_rating = Column(Float, nullable=True)
    review_count = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, default=True)
    is_accepting_students = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    bookings = relationship("TutorBooking", back_populates="tutor", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tutor_profiles_user", "user_id"),
        Index("ix_tutor_profiles_active", "is_active"),
        Index("ix_tutor_profiles_rate", "hourly_rate_cad"),
    )
