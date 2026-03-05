import enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class WaitlistStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REGISTERED = "registered"
    DECLINED = "declined"


class WaitlistEntry(Base):
    __tablename__ = "waitlist_entries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    roles = Column(String(255), nullable=True)  # JSON-encoded list of desired roles
    status = Column(String(20), nullable=False, default=WaitlistStatus.PENDING.value)
    admin_notes = Column(Text, nullable=True)

    # Invite / approval tracking
    invite_token = Column(String(255), unique=True, nullable=True, index=True)
    invite_token_expires_at = Column(DateTime(timezone=True), nullable=True)
    email_validated = Column(Boolean, default=False)

    # Approval info
    approved_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # Registration link
    registered_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Reminder tracking
    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    approved_by = relationship("User", foreign_keys=[approved_by_user_id])
    registered_user = relationship("User", foreign_keys=[registered_user_id])
