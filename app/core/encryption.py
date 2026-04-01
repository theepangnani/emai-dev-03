"""Fernet-based encryption for sensitive data at rest (e.g. OAuth tokens).

If TOKEN_ENCRYPTION_KEY is not set, tokens are stored/returned as plaintext
for backward compatibility and local development.
"""

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet | None:
    """Lazily initialise Fernet cipher from the configured key."""
    global _fernet
    if _fernet is not None:
        return _fernet
    key = settings.token_encryption_key
    if not key:
        return None
    try:
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
        return _fernet
    except (ValueError, TypeError) as exc:
        logger.error("Invalid TOKEN_ENCRYPTION_KEY — tokens will NOT be encrypted: %s", exc)
        return None


def encrypt_token(plaintext: str | None) -> str | None:
    """Encrypt a token string. Returns ciphertext or plaintext if no key."""
    if not plaintext:
        return plaintext
    f = _get_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(stored: str | None) -> str | None:
    """Decrypt a stored token. Falls back to returning the value as-is
    when it was stored before encryption was enabled (not a valid Fernet token)."""
    if not stored:
        return stored
    f = _get_fernet()
    if f is None:
        return stored
    try:
        return f.decrypt(stored.encode()).decode()
    except InvalidToken:
        # Value was stored as plaintext before encryption was enabled
        return stored
