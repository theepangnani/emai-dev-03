"""
Email Thread and Message models for the AI Email Agent (Phase 5).

Tracks outbound (ClassBridge-sent) and inbound (SendGrid webhook) emails,
grouped into threads for conversation-style display and AI summarisation.
"""
import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class EmailDirection(str, enum.Enum):
    OUTBOUND = "outbound"   # sent by user via ClassBridge
    INBOUND = "inbound"     # received reply via SendGrid Inbound Parse


class EmailStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RECEIVED = "received"


class EmailThread(Base):
    """Groups related email messages into a conversation thread."""

    __tablename__ = "email_threads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    subject = Column(String(500), nullable=False)

    # SendGrid Message-ID header stored so inbound replies can be matched back
    external_thread_id = Column(String(255), nullable=True, index=True)

    # JSON-encoded list of email address strings, e.g. '["a@b.com","c@d.com"]'
    recipient_emails = Column(Text, nullable=False, default="[]")
    # JSON-encoded list of display names matching recipient_emails order
    recipient_names = Column(Text, nullable=False, default="[]")

    message_count = Column(Integer, nullable=False, default=0)
    last_message_at = Column(DateTime(timezone=True), nullable=True)

    # AI-generated 2-4 sentence thread summary
    ai_summary = Column(Text, nullable=True)
    ai_summary_generated_at = Column(DateTime(timezone=True), nullable=True)

    # JSON-encoded list of tags: "parent", "teacher", "urgent", etc.
    tags = Column(Text, nullable=False, default="[]")

    is_archived = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    messages = relationship(
        "EmailMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="EmailMessage.created_at",
    )


class EmailMessage(Base):
    """A single email message belonging to a thread."""

    __tablename__ = "email_messages"

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("email_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    direction = Column(Enum(EmailDirection), nullable=False)

    from_email = Column(String(255), nullable=False)
    from_name = Column(String(255), nullable=True)

    # JSON-encoded list of recipient email strings
    to_emails = Column(Text, nullable=False, default="[]")

    subject = Column(String(500), nullable=False)

    # Plain-text body (always present)
    body_text = Column(Text, nullable=False, default="")
    # Optional HTML body
    body_html = Column(Text, nullable=True)

    # SendGrid X-Message-Id header returned after successful send
    sendgrid_message_id = Column(String(255), nullable=True, index=True)

    # True if the body was initially drafted by the AI assistant
    ai_draft = Column(Boolean, nullable=False, default=False)
    # Tone requested when AI drafted: "formal", "friendly", "concise", "empathetic"
    ai_tone = Column(String(50), nullable=True)

    status = Column(Enum(EmailStatus), nullable=False, default=EmailStatus.DRAFT)

    sent_at = Column(DateTime(timezone=True), nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    thread = relationship("EmailThread", back_populates="messages")
    user = relationship("User", foreign_keys=[user_id])
