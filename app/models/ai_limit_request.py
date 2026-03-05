import enum

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class AILimitRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"


class AILimitRequest(Base):
    __tablename__ = "ai_limit_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_amount = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")

    # Admin resolution
    approved_amount = Column(Integer, nullable=True)
    admin_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])
    admin_user = relationship("User", foreign_keys=[admin_user_id])
