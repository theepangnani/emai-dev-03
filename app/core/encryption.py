"""
AES-256 symmetric encryption utilities for storing sensitive user data (BYOK — #578).

Keys are derived from the application SECRET_KEY via SHA-256 so no separate
key-management secret is required in development. In production the SECRET_KEY
must already be a strong random value (enforced by config.py).

IMPORTANT: Never log the plaintext value returned by decrypt_key().
"""
import base64
import hashlib

from cryptography.fernet import Fernet

from app.core.config import settings


def _get_fernet() -> Fernet:
    """Derive a stable Fernet key from the application SECRET_KEY."""
    raw = hashlib.sha256(settings.secret_key.encode()).digest()  # 32 bytes
    key = base64.urlsafe_b64encode(raw)                          # Fernet requires URL-safe base64
    return Fernet(key)


def encrypt_key(api_key: str) -> str:
    """Encrypt *api_key* and return the ciphertext as a URL-safe string."""
    return _get_fernet().encrypt(api_key.encode()).decode()


def decrypt_key(encrypted: str) -> str:
    """Decrypt the ciphertext produced by *encrypt_key* and return the plaintext."""
    return _get_fernet().decrypt(encrypted.encode()).decode()
