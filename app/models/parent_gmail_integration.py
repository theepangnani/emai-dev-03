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
    monitored_emails = relationship("ParentDigestMonitoredEmail", back_populates="integration", cascade="all, delete-orphan")


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


class ParentDigestMonitoredEmail(Base):
    __tablename__ = "parent_digest_monitored_emails"
    __table_args__ = (
        UniqueConstraint("integration_id", "email_address", name="uq_integration_monitored_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("parent_gmail_integrations.id", ondelete="CASCADE"), nullable=False, index=True)
    email_address = Column(String(255), nullable=True)
    label = Column(String(100), nullable=True)
    sender_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    integration = relationship("ParentGmailIntegration", back_populates="monitored_emails")


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
    whatsapp_delivery_status = Column(String(20), nullable=True)  # "sent", "failed", "skipped", or None if not attempted
    email_delivery_status = Column(String(20), nullable=True)  # "sent", "failed", "skipped", or None if not attempted (#3880)

    parent = relationship("User")
    integration = relationship("ParentGmailIntegration", back_populates="delivery_logs")


# ---------------------------------------------------------------------------
# Unified Digest v2 — parent-level tables (#4012, #4013)
# Decouples sender identity from integration identity, enables one sender to
# apply to multiple kids, and adds school-email attribution via `To:` headers.
# ---------------------------------------------------------------------------

class ParentChildProfile(Base):
    __tablename__ = "parent_child_profiles"
    __table_args__ = (
        UniqueConstraint("parent_id", "student_id", name="uq_parent_child_profile_student"),
    )

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    first_name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parent = relationship("User", foreign_keys=[parent_id])
    student = relationship("User", foreign_keys=[student_id])
    school_emails = relationship("ParentChildSchoolEmail", back_populates="child_profile", cascade="all, delete-orphan")
    sender_assignments = relationship("SenderChildAssignment", back_populates="child_profile", cascade="all, delete-orphan")


class ParentChildSchoolEmail(Base):
    __tablename__ = "parent_child_school_emails"
    __table_args__ = (
        UniqueConstraint("child_profile_id", "email_address", name="uq_child_school_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    child_profile_id = Column(Integer, ForeignKey("parent_child_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    email_address = Column(String(255), nullable=False, index=True)
    forwarding_seen_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    child_profile = relationship("ParentChildProfile", back_populates="school_emails")


class ParentDigestMonitoredSender(Base):
    __tablename__ = "parent_digest_monitored_senders"
    __table_args__ = (
        UniqueConstraint("parent_id", "email_address", name="uq_parent_monitored_sender_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email_address = Column(String(255), nullable=True)
    sender_name = Column(String(100), nullable=True)
    label = Column(String(100), nullable=True)
    applies_to_all = Column(Boolean, server_default=text("false"), default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parent = relationship("User")
    child_assignments = relationship("SenderChildAssignment", back_populates="sender", cascade="all, delete-orphan")


class SenderChildAssignment(Base):
    __tablename__ = "sender_child_assignments"
    __table_args__ = (
        UniqueConstraint("sender_id", "child_profile_id", name="uq_sender_child_assignment"),
    )

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("parent_digest_monitored_senders.id", ondelete="CASCADE"), nullable=False, index=True)
    child_profile_id = Column(Integer, ForeignKey("parent_child_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sender = relationship("ParentDigestMonitoredSender", back_populates="child_assignments")
    child_profile = relationship(
        "ParentChildProfile",
        back_populates="sender_assignments",
        lazy="selectin",
    )


# ---------------------------------------------------------------------------
# Auto-discovered school addresses (#4329)
# Surface unregistered school-looking To: addresses so the parent can assign
# them to a kid (or dismiss). Filled by the worker on each digest run.
# ---------------------------------------------------------------------------

class ParentDiscoveredSchoolEmail(Base):
    __tablename__ = "parent_discovered_school_emails"
    __table_args__ = (
        UniqueConstraint("parent_id", "email_address", name="uq_parent_discovered_email"),
    )

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email_address = Column(String(255), nullable=False, index=True)
    sample_sender = Column(String(255), nullable=True)
    occurrences = Column(Integer, nullable=False, default=1)
    first_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
