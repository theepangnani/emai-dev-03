"""Two-factor authentication model (TOTP)."""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from app.db.database import Base


class TOTPDevice(Base):
    """Stores per-user TOTP device configuration.

    Each user may have at most one TOTPDevice (enforced by the unique
    constraint on user_id).  The device is created during setup but
    is *not* enabled until the user successfully verifies their first
    TOTP code, confirming they have properly enrolled their authenticator
    app.
    """

    __tablename__ = "totp_devices"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Base32-encoded TOTP secret (stored XOR-obfuscated with SECRET_KEY)
    secret = Column(String(512), nullable=False)

    # Whether 2FA is currently active for this user
    is_enabled = Column(Boolean, default=False, nullable=False)

    # Timestamp when the user first verified the device
    verified_at = Column(DateTime(timezone=True), nullable=True)

    # 8 one-time-use backup codes (JSON list of strings)
    backup_codes = Column(JSON, nullable=True, default=list)

    # Backup codes that have already been consumed (JSON list of strings)
    used_backup_codes = Column(JSON, nullable=True, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
