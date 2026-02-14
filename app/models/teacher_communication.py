import enum

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class CommunicationType(str, enum.Enum):
    EMAIL = "email"
    ANNOUNCEMENT = "announcement"
    COMMENT = "comment"


class TeacherCommunication(Base):
    __tablename__ = "teacher_communications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(CommunicationType), nullable=False)

    # Source identification (dedup key)
    source_id = Column(String(255), nullable=False, index=True)

    # Sender info
    sender_name = Column(String(255), nullable=True)
    sender_email = Column(String(255), nullable=True)

    # Content
    subject = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    snippet = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)

    # Context (for Classroom items)
    course_name = Column(String(255), nullable=True)
    course_id = Column(String(255), nullable=True)

    # Metadata
    received_at = Column(DateTime(timezone=True), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        Index("ix_teacher_comm_user_source", "user_id", "source_id", unique=True),
    )
