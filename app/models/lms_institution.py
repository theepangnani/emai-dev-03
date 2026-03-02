"""LMSInstitution model — represents a school board or institution's LMS instance."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func

from app.db.database import Base


class LMSInstitution(Base):
    """A school board or institution that operates an LMS instance.

    Examples:
    - TDSB Brightspace at tdsb.brightspace.com
    - PDSB Brightspace at peel.brightspace.com
    - Google Classroom (no base_url needed)
    """

    __tablename__ = "lms_institutions"

    id = Column(Integer, primary_key=True, index=True)

    # Human-readable name e.g. "TDSB Brightspace", "PDSB Google Classroom"
    name = Column(String(255), nullable=False)

    # Provider identifier: "google_classroom" | "brightspace" | "canvas" | "moodle"
    provider = Column(String(50), nullable=False, index=True)

    # Base URL for the institution's LMS instance (None for Google Classroom)
    # e.g. "https://tdsb.brightspace.com"
    base_url = Column(String(500), nullable=True)

    # Canadian province/region code e.g. "ON", "BC", "AB"
    region = Column(String(10), nullable=True)

    # Whether this institution is currently accepting new connections
    is_active = Column(Boolean, nullable=False, default=True)

    # Provider-specific configuration as JSON string
    # e.g. OAuth client IDs, custom endpoints
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
