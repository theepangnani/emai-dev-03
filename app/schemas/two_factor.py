"""Pydantic schemas for two-factor authentication (TOTP)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TOTPSetupResponse(BaseModel):
    """Returned when the user initiates 2FA setup."""

    secret: str = Field(..., description="Base32 TOTP secret for manual entry")
    qr_code_url: str = Field(
        ..., description="base64 PNG data URL of the QR code to scan"
    )
    backup_codes: list[str] = Field(
        ..., description="8 one-time backup codes — save these securely"
    )


class TOTPVerifyRequest(BaseModel):
    """Body for verifying a TOTP code (enable / disable / verify endpoints)."""

    code: str = Field(..., min_length=6, max_length=8, description="6-digit TOTP code")


class TOTPLoginRequest(BaseModel):
    """Body for the second step of the 2FA login flow."""

    temp_token: str = Field(..., description="Short-lived token returned after password check")
    code: str = Field(..., min_length=6, max_length=8, description="6-digit TOTP code or backup code")


class TOTPStatusResponse(BaseModel):
    """Current 2FA status for the authenticated user."""

    is_enabled: bool
    has_device: bool


class BackupCodesResponse(BaseModel):
    """Masked backup codes list."""

    backup_codes: list[str]
    used_count: int
    total: int
