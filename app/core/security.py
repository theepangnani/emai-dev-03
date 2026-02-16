import re
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt

from app.core.config import settings

# Minimum 8 chars, at least one uppercase, one lowercase, one digit, one special char
_PASSWORD_MIN_LENGTH = 8
_PASSWORD_PATTERN = re.compile(
    r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};\':\"\\|,.<>\/?`~]).+$'
)


# Sentinel hash for accounts that cannot log in with a password (e.g. parent-created
# child accounts that must set their password via invite link). bcrypt hashes always
# start with "$2b$" so this value will never match any real password check.
UNUSABLE_PASSWORD_HASH = "!INVITE_PENDING"


def validate_password_strength(password: str) -> str | None:
    """Return an error message if the password is too weak, or None if OK."""
    if len(password) < _PASSWORD_MIN_LENGTH:
        return f"Password must be at least {_PASSWORD_MIN_LENGTH} characters"
    if not _PASSWORD_PATTERN.match(password):
        return "Password must include uppercase, lowercase, digit, and special character"
    return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password or hashed_password == UNUSABLE_PASSWORD_HASH:
        return False
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access", "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh", "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_refresh_token(token: str) -> dict | None:
    """Decode and validate a refresh token. Returns payload or None."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "refresh":
            return None
        return payload
    except Exception:
        return None


def create_password_reset_token(email: str) -> str:
    """Create a JWT for password reset (1-hour expiry)."""
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    to_encode = {"sub": email, "exp": expire, "type": "password_reset"}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_password_reset_token(token: str) -> str | None:
    """Decode a password-reset JWT. Returns the email or None."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "password_reset":
            return None
        return payload.get("sub")
    except Exception:
        return None


def create_email_verification_token(email: str) -> str:
    """Create a JWT for email verification (24-hour expiry)."""
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode = {"sub": email, "exp": expire, "type": "email_verify"}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_email_verification_token(token: str) -> str | None:
    """Decode an email-verification JWT. Returns the email or None."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "email_verify":
            return None
        return payload.get("sub")
    except Exception:
        return None
