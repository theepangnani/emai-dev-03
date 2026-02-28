import enum

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class LinkRequestType(str, enum.Enum):
    PARENT_TO_STUDENT = "parent_to_student"
    STUDENT_TO_PARENT = "student_to_parent"


class LinkRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class LinkRequest(Base):
    __tablename__ = "link_requests"

    id = Column(Integer, primary_key=True, index=True)
    request_type = Column(String(30), nullable=False)
    status = Column(String(20), default="pending", nullable=False)

    requester_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=True)

    relationship_type = Column(String(20), default="guardian")
    message = Column(Text, nullable=True)

    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    requester = relationship("User", foreign_keys=[requester_user_id])
    target = relationship("User", foreign_keys=[target_user_id])

    __table_args__ = (
        Index("ix_link_requests_target_status", "target_user_id", "status"),
        Index("ix_link_requests_requester", "requester_user_id"),
    )
