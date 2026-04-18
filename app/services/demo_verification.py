"""Demo verification service (CB-DEMO-001 F3, #3602).

Issues and verifies credentials for a demo session:
  1. A 72-hour magic-link token (32-byte urlsafe random; PRD §12.3).
  2. A 6-digit numeric fallback code for users who can't use the link.

Only SHA-256 hashes are persisted on the ``demo_sessions`` row. Raw values
are returned to the caller exactly once, emailed to the user, and then
discarded. On a successful verification the token/code hash columns are
cleared so the credential cannot be replayed.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.demo_session import DemoSession

logger = logging.getLogger(__name__)

# PRD §12.3 — 72h demo verification window. Falls back to the generic
# email-verify TTL if an override isn't configured, else 72h.
_DEFAULT_EXPIRE_HOURS = 72


def _expire_hours() -> int:
    """Return the demo verification TTL in hours."""
    configured = getattr(settings, "email_verify_token_expire_hours", None)
    if configured and configured >= 72:
        return int(configured)
    return _DEFAULT_EXPIRE_HOURS


def _sha256_hex(value: str) -> str:
    """Return the hex sha256 digest of ``value``."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalise a datetime to timezone-aware UTC for safe comparison."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_magic_link_token(session_id: str, email: str) -> tuple[str, str]:
    """Create a fresh magic-link token for a demo session.

    Args:
        session_id: ``demo_sessions.id`` — accepted for logging/observability.
        email: Recipient email — accepted for logging/observability.

    Returns:
        Tuple of ``(raw_token, token_hash)``. The raw token is 32 bytes of
        urlsafe random data (≈43 chars) and MUST only be emailed, never
        stored. Only ``token_hash`` (hex sha256) is safe to persist.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = _sha256_hex(raw_token)
    logger.info(
        "demo_verification: issued magic link token | session_id=%s", session_id
    )
    return raw_token, token_hash


def create_fallback_code() -> tuple[str, str]:
    """Create a fresh 6-digit fallback code.

    Returns:
        Tuple of ``(raw_code, code_hash)``. ``raw_code`` is always a
        zero-padded 6-digit numeric string in ``"000000".."999999"``.
        Only ``code_hash`` is safe to persist.
    """
    # secrets.randbelow(900_000) + 100_000 avoids leading-zero values
    # but per spec we want uniform 100000..999999 inclusive.
    raw_code = f"{secrets.randbelow(900_000) + 100_000:06d}"
    code_hash = _sha256_hex(raw_code)
    return raw_code, code_hash


def set_verification_credentials(
    db: Session,
    demo_session: DemoSession,
    *,
    token_hash: str,
    code_hash: str,
) -> DemoSession:
    """Persist hashed credentials and expiry timestamps on the session.

    Does not commit — the caller is responsible for committing the
    surrounding transaction.
    """
    expires_at = _utcnow() + timedelta(hours=_expire_hours())
    demo_session.verification_token_hash = token_hash
    demo_session.verification_expires_at = expires_at
    demo_session.fallback_code_hash = code_hash
    demo_session.fallback_code_expires_at = expires_at
    return demo_session


def _mark_verified(db: Session, demo_session: DemoSession) -> None:
    """Mark ``demo_session`` verified and clear single-use credentials."""
    demo_session.verified = True
    demo_session.verified_ts = _utcnow()
    # Single-use: clear hashes so link/code cannot be replayed.
    demo_session.verification_token_hash = None
    demo_session.verification_expires_at = None
    demo_session.fallback_code_hash = None
    demo_session.fallback_code_expires_at = None
    db.commit()
    db.refresh(demo_session)


def verify_magic_link(db: Session, raw_token: str) -> Optional[DemoSession]:
    """Verify a raw magic-link token.

    Returns the matching ``DemoSession`` iff:
      * a row exists with ``verification_token_hash == sha256(raw_token)``
      * ``verification_expires_at`` is in the future (UTC)
      * the session is not already ``verified`` (prevents replay)

    On success the session's credential columns are cleared and
    ``verified`` / ``verified_ts`` are set. The updated session is
    returned. Returns ``None`` on any mismatch without leaking detail.
    """
    if not raw_token:
        return None

    token_hash = _sha256_hex(raw_token)
    candidate = (
        db.query(DemoSession)
        .filter(DemoSession.verification_token_hash == token_hash)
        .first()
    )
    if candidate is None:
        return None
    if candidate.verified:
        # Already used — treat as replay attempt.
        return None

    expires_at = _as_utc(candidate.verification_expires_at)
    if expires_at is None or expires_at <= _utcnow():
        return None

    _mark_verified(db, candidate)
    return candidate


def verify_fallback_code(
    db: Session, email: str, raw_code: str
) -> Optional[DemoSession]:
    """Verify a raw 6-digit fallback code for the given email.

    Email comparison is case-insensitive. Returns the matching session
    iff the code hash matches, the code hasn't expired, and the session
    isn't already verified. On success the credentials are cleared and
    the session is marked verified.
    """
    if not email or not raw_code:
        return None

    code_hash = _sha256_hex(raw_code)
    normalised_email = email.strip().lower()

    # Case-insensitive email match; pick the most recent unverified row so
    # a fresh signup supersedes any older pending sessions for the same
    # address (the older rows will have their own hashes and simply won't
    # match).
    candidate = (
        db.query(DemoSession)
        .filter(func.lower(DemoSession.email) == normalised_email)
        .filter(DemoSession.fallback_code_hash == code_hash)
        .order_by(DemoSession.created_at.desc())
        .first()
    )
    if candidate is None:
        return None
    if candidate.verified:
        return None

    expires_at = _as_utc(candidate.fallback_code_expires_at)
    if expires_at is None or expires_at <= _utcnow():
        return None

    _mark_verified(db, candidate)
    return candidate
