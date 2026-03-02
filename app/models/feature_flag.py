import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.db.database import Base


class FlagScope(str, enum.Enum):
    GLOBAL = "global"   # on/off for everyone
    TIER = "tier"       # on for free/premium tier
    USER = "user"       # on for specific users
    ROLE = "role"       # on for specific roles
    BETA = "beta"       # on for beta users (opt-in)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    scope = Column(String(20), nullable=False, default=FlagScope.GLOBAL.value)
    is_enabled = Column(Boolean, nullable=False, default=False)

    # JSON lists stored as text
    enabled_tiers = Column(Text, nullable=False, default="[]")      # ["free", "premium"]
    enabled_roles = Column(Text, nullable=False, default="[]")      # ["teacher", "admin"]
    enabled_user_ids = Column(Text, nullable=False, default="[]")   # [1, 2, 3]

    # Gradual rollout percentage for GLOBAL scope (0-100)
    rollout_percentage = Column(Integer, nullable=False, default=100)

    # Extra metadata (e.g. max_value, config)
    metadata_json = Column(Text, nullable=False, default="{}")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class UserFeatureOverride(Base):
    __tablename__ = "user_feature_overrides"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flag_key = Column(String(100), nullable=False, index=True)
    is_enabled = Column(Boolean, nullable=False)
    reason = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "flag_key", name="uq_user_flag"),)
