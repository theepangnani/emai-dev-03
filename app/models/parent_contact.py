from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.database import Base


class ParentContact(Base):
    __tablename__ = "parent_contacts"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(20), nullable=True)  # E.164 format
    school_name = Column(String(255), nullable=True, index=True)
    child_name = Column(String(255), nullable=True)
    child_grade = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, default="lead")  # lead/contacted/interested/converted/archived/unresponsive
    source = Column(String(50), nullable=False, default="manual")  # manual/csv_import/waitlist/referral
    tags = Column(JSON, nullable=True, default=list)  # Array of strings
    linked_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    consent_given = Column(Boolean, nullable=False, default=False)
    consent_date = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    notes = relationship("ParentContactNote", back_populates="contact", cascade="all, delete-orphan", lazy="dynamic")
    outreach_logs = relationship("OutreachLog", back_populates="contact", lazy="dynamic")

    __table_args__ = (
        Index("ix_parent_contacts_status", "status"),
        Index("ix_parent_contacts_created_by", "created_by_user_id"),
        Index("ix_parent_contacts_linked_user", "linked_user_id"),
    )


class ParentContactNote(Base):
    __tablename__ = "parent_contact_notes"

    id = Column(Integer, primary_key=True, index=True)
    parent_contact_id = Column(Integer, ForeignKey("parent_contacts.id", ondelete="CASCADE"), nullable=False)
    note_text = Column(Text, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    contact = relationship("ParentContact", back_populates="notes")

    __table_args__ = (
        Index("ix_parent_contact_notes_contact_created", "parent_contact_id", "created_at"),
    )


class OutreachTemplate(Base):
    __tablename__ = "outreach_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    subject = Column(String(500), nullable=True)  # Email only
    body_html = Column(Text, nullable=True)  # Email HTML
    body_text = Column(Text, nullable=False)  # Plain text / WhatsApp / SMS
    template_type = Column(String(20), nullable=False, default="email")  # email/whatsapp/sms
    variables = Column(JSON, nullable=True, default=list)  # List of variable names
    is_active = Column(Boolean, nullable=False, default=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_outreach_templates_type_active", "template_type", "is_active"),
    )


class OutreachLog(Base):
    __tablename__ = "outreach_log"

    id = Column(Integer, primary_key=True, index=True)
    parent_contact_id = Column(Integer, ForeignKey("parent_contacts.id", ondelete="SET NULL"), nullable=True)
    template_id = Column(Integer, ForeignKey("outreach_templates.id", ondelete="SET NULL"), nullable=True)
    channel = Column(String(20), nullable=False)  # email/whatsapp/sms
    status = Column(String(20), nullable=False)  # sent/failed/delivered/bounced
    recipient_detail = Column(String(255), nullable=True)  # email or phone at time of send
    body_snapshot = Column(Text, nullable=True)  # Rendered body at send time
    sent_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    contact = relationship("ParentContact", back_populates="outreach_logs")

    __table_args__ = (
        Index("ix_outreach_log_contact", "parent_contact_id"),
        Index("ix_outreach_log_sent_by_created", "sent_by_user_id", "created_at"),
        Index("ix_outreach_log_channel_status", "channel", "status"),
    )
