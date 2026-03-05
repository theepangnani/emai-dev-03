"""Waitlist model — tracks users who sign up before they're approved to register."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from app.db.database import Base


class Waitlist(Base):
    __tablename__ = "waitlist"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    roles = Column(JSON, nullable=False)  # e.g. ["parent", "student"]
    status = Column(String(20), nullable=False, default="pending")  # pending, approved, rejected
    admin_notes = Column(String(1000), nullable=True)

    # Invite token (generated when admin approves)
    invite_token = Column(String(255), nullable=True, unique=True, index=True)
    invite_token_expires_at = Column(DateTime(timezone=True), nullable=True)

    email_validated = Column(Boolean, default=False)

    # Admin who approved
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Link to the user record once they register
    registered_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
