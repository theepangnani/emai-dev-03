"""TutorMatchPreference — per-user matching preference settings for AI Tutor Matching (Phase 4)."""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class TutorMatchPreference(Base):
    """Stores a user's preferences for the AI tutor matching algorithm."""

    __tablename__ = "tutor_match_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Budget preference
    max_hourly_rate_cad = Column(Float, nullable=True)   # None means no limit

    # Subject preferences (JSON list of subject name strings)
    preferred_subjects = Column(String(1024), default="[]")

    # Grade level preferences (JSON list of grade strings)
    preferred_grade_levels = Column(String(512), default="[]")

    # Availability preferences (JSON list: ["Monday evening", "Tuesday afternoon"])
    preferred_availability = Column(String(1024), default="[]")

    # Quality / verification filters
    min_rating = Column(Float, default=3.0)
    prefer_verified_only = Column(Boolean, default=False)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_tutor_match_preferences_user", "user_id"),
    )
