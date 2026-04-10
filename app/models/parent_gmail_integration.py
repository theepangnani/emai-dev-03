from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ParentGmailIntegration(Base):
    __tablename__ = "parent_gmail_integrations"
    __table_args__ = (
        UniqueConstraint("parent_id", "child_school_email", name="uq_parent_child_school_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    gmail_address = Column(String(255), nullable=False)
    google_id = Column(String(255), nullable=True)
    access_token = Column(String(2048), nullable=True)
    refresh_token = Column(String(1024), nullable=True)
    child_school_email = Column(String(255), nullable=True)
    child_first_name = Column(String(100), nullable=True)
    connected_at = Column(DateTime(timezone=True), server_default=func.now())
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, server_default=text("true"), default=True)
    paused_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    whatsapp_phone = Column(String(20), nullable=True)
    whatsapp_verified = Column(Boolean, server_default=text("false"), default=False)
    whatsapp_otp_code = Column(String(6), nullable=True)
    whatsapp_otp_expires_at = Column(DateTime(timezone=True), nullable=True)

    parent = relationship("User", backref="gmail_integrations")
    digest_settings = relationship("ParentDigestSettings", back_populates="integration", uselist=False, cascade="all, delete-orphan")
    delivery_logs = relationship("DigestDeliveryLog", back_populates="integration", cascade="all, delete-orphan")


class ParentDigestSettings(Base):
    __tablename__ = "parent_digest_settings"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("parent_gmail_integrations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    digest_enabled = Column(Boolean, server_default=text("true"), default=True)
    delivery_time = Column(String(5), default="07:00")
    timezone = Column(String(50), default="America/Toronto")
    digest_format = Column(String(20), default="full")
    delivery_channels = Column(String(50), default="in_app,email")
    notify_on_empty = Column(Boolean, server_default=text("false"), default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    integration = relationship("ParentGmailIntegration", back_populates="digest_settings")


class DigestDeliveryLog(Base):
    __tablename__ = "digest_delivery_log"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    integration_id = Column(Integer, ForeignKey("parent_gmail_integrations.id", ondelete="CASCADE"), nullable=False, index=True)
    email_count = Column(Integer, nullable=False, default=0)
    digest_content = Column(Text, nullable=True)
    digest_length_chars = Column(Integer, nullable=True)
    delivered_at = Column(DateTime(timezone=True), server_default=func.now())
    channels_used = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="delivered")

    parent = relationship("User")
    integration = relationship("ParentGmailIntegration", back_populates="delivery_logs")
