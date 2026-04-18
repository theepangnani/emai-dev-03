"""Demo Session model for CB-DEMO-001 Instant Trial & Demo Experience (#3600)."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.core.config import settings
from app.db.database import Base


_IS_PG = "sqlite" not in settings.database_url


if _IS_PG:
    from sqlalchemy.dialects.postgresql import JSONB, UUID

    _JSONType = JSONB
    _IDColumn = lambda: Column(  # noqa: E731
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
else:
    _JSONType = JSON

    def _IDColumn():  # type: ignore[no-redef]
        return Column(
            String(36),
            primary_key=True,
            default=lambda: str(uuid.uuid4()),
        )


class DemoSession(Base):
    """Demo session record for unauthenticated trial users (PRD §11.5)."""

    __tablename__ = "demo_sessions"

    id = _IDColumn()
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # Case-insensitivity is enforced at the DB layer (CITEXT on PG,
    # COLLATE NOCASE on SQLite) — Python-side `==` comparisons on the
    # `email` column still need a lowered hash or explicit ilike.
    email_hash = Column(String(64), nullable=False)
    email = Column(Text, nullable=False)
    full_name = Column(Text, nullable=True)
    # role: 'parent' | 'student' | 'teacher' | 'other'
    role = Column(String(10), nullable=False)
    consent_ts = Column(DateTime(timezone=True), nullable=True)
    verified = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="FALSE",
    )
    verified_ts = Column(DateTime(timezone=True), nullable=True)
    verification_token_hash = Column(String(64), nullable=True)
    verification_expires_at = Column(DateTime(timezone=True), nullable=True)
    fallback_code_hash = Column(String(64), nullable=True)
    fallback_code_expires_at = Column(DateTime(timezone=True), nullable=True)
    generations_count = Column(Integer, nullable=False, default=0, server_default="0")
    generations_json = Column(_JSONType, nullable=True)
    moat_engagement_json = Column(_JSONType, nullable=True)
    source_ip_hash = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    # admin_status: 'pending' | 'approved' | 'rejected' | 'blocklisted'
    admin_status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "role IN ('parent', 'student', 'teacher', 'other')",
            name="ck_demo_sessions_role",
        ),
        CheckConstraint(
            "admin_status IN ('pending', 'approved', 'rejected', 'blocklisted')",
            name="ck_demo_sessions_admin_status",
        ),
        Index("idx_demo_sessions_email_hash", "email_hash"),
    )
