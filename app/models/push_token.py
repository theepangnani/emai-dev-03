import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class DevicePlatform(str, enum.Enum):
    WEB = "web"
    IOS = "ios"
    ANDROID = "android"


class PushToken(Base):
    __tablename__ = "push_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # FCM registration token — unique per token string
    token = Column(String(512), nullable=False, unique=True, index=True)
    platform = Column(Enum(DevicePlatform), nullable=False, default=DevicePlatform.WEB)

    # Human-readable device info ("iPhone 15", "Chrome on Windows")
    device_name = Column(String(255), nullable=True)
    app_version = Column(String(50), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="push_tokens")

    __table_args__ = (
        Index("ix_push_tokens_user_active", "user_id", "is_active"),
    )
