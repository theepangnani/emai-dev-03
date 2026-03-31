"""Parent Gmail Integration models for Email Digest feature.

Stub file — will be replaced with full implementation when the models branch is merged.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class ParentGmailIntegration(Base):
    __tablename__ = "parent_gmail_integrations"

    id = Column(Integer, primary_key=True, index=True)
    parent_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    gmail_address = Column(String(255), nullable=False)
    status = Column(String(20), default="active")  # active, disconnected, error
    paused_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    settings = relationship("ParentDigestSettings", back_populates="integration", uselist=False)
    delivery_logs = relationship("DigestDeliveryLog", back_populates="integration")


class ParentDigestSettings(Base):
    __tablename__ = "parent_digest_settings"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("parent_gmail_integrations.id", ondelete="CASCADE"), nullable=False, unique=True)
    delivery_time = Column(String(5), default="08:00")  # HH:MM format
    timezone = Column(String(50), default="America/Toronto")
    include_ai_summary = Column(Boolean, default=True)
    include_action_items = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    integration = relationship("ParentGmailIntegration", back_populates="settings")


class DigestDeliveryLog(Base):
    __tablename__ = "digest_delivery_logs"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("parent_gmail_integrations.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False)  # delivered, failed, skipped
    email_count = Column(Integer, default=0)
    digest_content = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    integration = relationship("ParentGmailIntegration", back_populates="delivery_logs")
