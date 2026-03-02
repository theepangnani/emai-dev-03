"""
APIKey model — bcrypt-hashed keys with cbk_ prefix for MCP and external integrations (#905).
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # The full key is never stored — only a bcrypt hash and the short prefix for display
    key_hash = Column(String(255), nullable=False)
    key_prefix = Column(String(20), nullable=False)  # first 8 chars, e.g. "cbk_a1b2"

    name = Column(String(100), nullable=False)  # user-defined label
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="api_keys")
