from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index
from sqlalchemy.sql import func

from app.db.database import Base


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(36), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), server_default=func.now())
    reason = Column(String(50), nullable=True)  # "logout", "password_change", "admin_revoke"

    __table_args__ = (
        Index("ix_token_blacklist_expires", "expires_at"),
    )
