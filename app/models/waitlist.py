from enum import Enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from app.db.database import Base


class WaitlistStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    REGISTERED = "registered"


class Waitlist(Base):
    __tablename__ = "waitlist"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    roles = Column(JSON, nullable=True)  # Array of selected roles e.g. ["parent", "student"]
    status = Column(String(20), nullable=False, default="pending")  # pending/approved/declined/registered
    admin_notes = Column(String, nullable=True)  # TEXT
    invite_token = Column(String(255), nullable=True, unique=True, index=True)
    invite_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    invite_link_clicked = Column(Boolean, default=False)
    approved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    registered_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Alias used by admin_waitlist routes
WaitlistEntry = Waitlist
