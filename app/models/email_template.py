from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # e.g. "welcome", "invite_student"
    subject = Column(String(255), nullable=False)
    html_body = Column(Text, nullable=False)
    text_body = Column(Text, nullable=True)
    description = Column(String(255), nullable=True)  # admin-facing description
    is_customized = Column(Boolean, default=False)  # False = using default
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    updated_by = relationship("User", foreign_keys=[updated_by_id])
