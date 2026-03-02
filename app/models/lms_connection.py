"""LMSConnection model — represents a user's connection to an LMS provider."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class LMSConnection(Base):
    """A user's connection/credentials to an LMS provider.

    A user can have multiple connections (e.g. personal Google Classroom +
    TDSB Brightspace + private tutor Google Classroom).
    """

    __tablename__ = "lms_connections"

    id = Column(Integer, primary_key=True, index=True)

    # Owner of this connection
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Optional institution (None for personal Google Classroom connections)
    institution_id = Column(
        Integer,
        ForeignKey("lms_institutions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Provider identifier: "google_classroom" | "brightspace" | "canvas"
    provider = Column(String(50), nullable=False)

    # User-defined label e.g. "TDSB School", "Private Tutor - Mr. Khan"
    label = Column(String(255), nullable=True)

    # Connection status
    # "connected"     — active and tokens are valid
    # "expired"       — tokens expired, re-auth required
    # "error"         — sync or auth error
    # "disconnected"  — user manually disconnected or OAuth not yet completed
    status = Column(String(20), nullable=False, default="connected")

    # OAuth tokens (stored encrypted — same pattern as User.google_access_token)
    access_token_enc = Column(Text, nullable=True)
    refresh_token_enc = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Sync metadata
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    sync_error = Column(Text, nullable=True)
    courses_synced = Column(Integer, nullable=False, default=0)

    # The user's ID in the external LMS (e.g. Brightspace user ID)
    external_user_id = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    institution = relationship("LMSInstitution", foreign_keys=[institution_id])

    __table_args__ = (
        Index("ix_lms_connections_user", "user_id"),
        Index("ix_lms_connections_provider", "provider"),
        Index("ix_lms_connections_user_provider", "user_id", "provider"),
    )
