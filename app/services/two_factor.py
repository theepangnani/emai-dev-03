"""Two-factor authentication service (TOTP via pyotp + qrcode)."""
from __future__ import annotations

import base64
import io
import secrets
import string
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.two_factor import TOTPDevice

# ---------------------------------------------------------------------------
# Optional dependency check — pyotp / qrcode are optional installs.
# We fail with a descriptive error at call time rather than at import time so
# that the rest of the application boots normally even if the packages are
# missing.
# ---------------------------------------------------------------------------

try:
    import pyotp  # type: ignore[import-not-found]
    _PYOTP_AVAILABLE = True
except ImportError:
    _PYOTP_AVAILABLE = False

try:
    import qrcode  # type: ignore[import-not-found]
    _QRCODE_AVAILABLE = True
except ImportError:
    _QRCODE_AVAILABLE = False


def _require_pyotp() -> None:
    if not _PYOTP_AVAILABLE:
        raise RuntimeError(
            "pyotp is not installed. Run: pip install 'pyotp>=2.9.0'"
        )


def _require_qrcode() -> None:
    if not _QRCODE_AVAILABLE:
        raise RuntimeError(
            "qrcode is not installed. Run: pip install 'qrcode[pil]>=7.4.2'"
        )


# ---------------------------------------------------------------------------
# Secret obfuscation helpers
# ---------------------------------------------------------------------------

def _get_key_bytes() -> bytes:
    """Derive a fixed-length key from the app SECRET_KEY."""
    from app.core.config import settings
    key_str = settings.secret_key or "classbridge-fallback-key"
    # Repeat/truncate to 32 bytes
    raw = key_str.encode("utf-8")
    return (raw * ((32 // len(raw)) + 1))[:32]


def _xor_obfuscate(data: str) -> str:
    """XOR-obfuscate *data* with the SECRET_KEY and return a hex string."""
    key = _get_key_bytes()
    data_bytes = data.encode("utf-8")
    xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(data_bytes))
    return xored.hex()


def _xor_deobfuscate(hex_str: str) -> str:
    """Reverse of _xor_obfuscate."""
    key = _get_key_bytes()
    xored = bytes.fromhex(hex_str)
    data_bytes = bytes(b ^ key[i % len(key)] for i, b in enumerate(xored))
    return data_bytes.decode("utf-8")


# ---------------------------------------------------------------------------
# TwoFactorService
# ---------------------------------------------------------------------------

class TwoFactorService:
    """Provides all business logic for TOTP-based 2FA."""

    # ------------------------------------------------------------------
    # Secret + provisioning URI helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_secret() -> str:
        """Return a random base32 TOTP secret (unobfuscated)."""
        _require_pyotp()
        return pyotp.random_base32()

    @staticmethod
    def get_provisioning_uri(secret: str, user_email: str) -> str:
        """Return an otpauth:// URI for QR code generation."""
        _require_pyotp()
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(user_email, issuer_name="ClassBridge")

    @staticmethod
    def generate_qr_code_base64(uri: str) -> str:
        """Return a base64 PNG data URL for the given OTP provisioning URI."""
        _require_qrcode()
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    # ------------------------------------------------------------------
    # Code verification
    # ------------------------------------------------------------------

    @staticmethod
    def verify_totp(secret: str, code: str) -> bool:
        """Return True if *code* is valid for *secret* (±30 s window)."""
        _require_pyotp()
        totp = pyotp.TOTP(secret)
        return bool(totp.verify(code, valid_window=1))

    # ------------------------------------------------------------------
    # Backup codes
    # ------------------------------------------------------------------

    @staticmethod
    def generate_backup_codes(count: int = 8) -> list[str]:
        """Return *count* random 8-character alphanumeric backup codes."""
        alphabet = string.ascii_uppercase + string.digits
        return [
            "".join(secrets.choice(alphabet) for _ in range(8))
            for _ in range(count)
        ]

    @staticmethod
    def verify_backup_code(device: "TOTPDevice", code: str) -> bool:
        """Return True if *code* is a valid unused backup code."""
        backup_codes: list[str] = device.backup_codes or []
        used: list[str] = device.used_backup_codes or []
        normalized = code.upper().strip()
        return normalized in backup_codes and normalized not in used

    @staticmethod
    def use_backup_code(device: "TOTPDevice", code: str, db: Session) -> "TOTPDevice":
        """Mark *code* as used and persist the change."""
        normalized = code.upper().strip()
        used: list[str] = list(device.used_backup_codes or [])
        if normalized not in used:
            used.append(normalized)
        device.used_backup_codes = used
        db.add(device)
        db.commit()
        db.refresh(device)
        return device

    # ------------------------------------------------------------------
    # Device lifecycle
    # ------------------------------------------------------------------

    @staticmethod
    def create_totp_device(
        user_id: int, user_email: str, db: Session
    ) -> tuple["TOTPDevice", str]:
        """Create (or reset) a TOTP device for *user_id*.

        Returns *(device, provisioning_uri)*.  The device is not yet enabled;
        the caller must call :meth:`enable_device` after the user verifies
        their first code.
        """
        from app.models.two_factor import TOTPDevice

        _require_pyotp()

        secret = TwoFactorService.generate_secret()
        uri = TwoFactorService.get_provisioning_uri(secret, user_email)
        backup_codes = TwoFactorService.generate_backup_codes()

        # Remove any existing device for this user
        existing = db.query(TOTPDevice).filter(TOTPDevice.user_id == user_id).first()
        if existing:
            db.delete(existing)
            db.flush()

        device = TOTPDevice(
            user_id=user_id,
            secret=_xor_obfuscate(secret),
            is_enabled=False,
            backup_codes=backup_codes,
            used_backup_codes=[],
        )
        db.add(device)
        db.commit()
        db.refresh(device)
        return device, uri

    @staticmethod
    def get_device_secret(device: "TOTPDevice") -> str:
        """Return the plaintext base32 secret from the stored obfuscated value."""
        return _xor_deobfuscate(device.secret)

    @staticmethod
    def enable_device(device: "TOTPDevice", db: Session) -> "TOTPDevice":
        """Mark the device as enabled and record the verification timestamp."""
        device.is_enabled = True
        device.verified_at = datetime.now(timezone.utc)
        db.add(device)
        db.commit()
        db.refresh(device)
        return device

    @staticmethod
    def disable_device(device: "TOTPDevice", db: Session) -> None:
        """Disable and delete the TOTP device, effectively turning off 2FA."""
        db.delete(device)
        db.commit()

    @staticmethod
    def regenerate_backup_codes(device: "TOTPDevice", db: Session) -> list[str]:
        """Generate a fresh set of backup codes, invalidating the old ones."""
        new_codes = TwoFactorService.generate_backup_codes()
        device.backup_codes = new_codes
        device.used_backup_codes = []
        db.add(device)
        db.commit()
        db.refresh(device)
        return new_codes

    # ------------------------------------------------------------------
    # Masked backup codes for display
    # ------------------------------------------------------------------

    @staticmethod
    def mask_backup_codes(codes: list[str], used: list[str]) -> list[str]:
        """Return masked representations: first 2 chars + *** (or USED)."""
        used_set = set(c.upper() for c in (used or []))
        masked: list[str] = []
        for code in codes or []:
            if code.upper() in used_set:
                masked.append(f"{code[:2]}*** (used)")
            else:
                masked.append(f"{code[:2]}***")
        return masked
