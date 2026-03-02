"""Two-factor authentication (TOTP) API routes.

Endpoints
---------
GET  /2fa/status                    — check if 2FA is enabled
POST /2fa/setup                     — generate secret + QR code
POST /2fa/enable                    — verify code and activate 2FA
POST /2fa/disable                   — verify code and deactivate 2FA
POST /2fa/verify                    — verify TOTP code (standalone, e.g. elevated actions)
GET  /2fa/backup-codes              — list masked backup codes
POST /2fa/backup-codes/regenerate   — regenerate backup codes
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.two_factor import TOTPDevice
from app.models.user import User
from app.schemas.two_factor import (
    BackupCodesResponse,
    TOTPSetupResponse,
    TOTPStatusResponse,
    TOTPVerifyRequest,
)
from app.services.two_factor import TwoFactorService

router = APIRouter(prefix="/2fa", tags=["Two-Factor Authentication"])
_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/status", response_model=TOTPStatusResponse)
def get_2fa_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return whether 2FA is set up and/or enabled for the current user."""
    device = (
        db.query(TOTPDevice)
        .filter(TOTPDevice.user_id == current_user.id)
        .first()
    )
    return TOTPStatusResponse(
        is_enabled=bool(device and device.is_enabled),
        has_device=device is not None,
    )


# ---------------------------------------------------------------------------
# Setup — generate secret + QR code
# ---------------------------------------------------------------------------

@router.post("/setup", response_model=TOTPSetupResponse)
def setup_2fa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initiate 2FA enrollment.

    Creates (or resets) a TOTP device for the current user and returns the
    secret, a QR code, and a fresh set of backup codes.  2FA is NOT yet
    enabled — the user must call POST /2fa/enable with a valid code first.
    """
    try:
        device, uri = TwoFactorService.create_totp_device(
            user_id=current_user.id,
            user_email=current_user.email or current_user.full_name,
            db=db,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )

    try:
        qr_code_url = TwoFactorService.generate_qr_code_base64(uri)
    except RuntimeError as exc:
        # qrcode not installed — return the URI as a fallback
        _logger.warning("QR code generation unavailable: %s", exc)
        qr_code_url = uri  # frontend can render it with a JS library

    plaintext_secret = TwoFactorService.get_device_secret(device)
    return TOTPSetupResponse(
        secret=plaintext_secret,
        qr_code_url=qr_code_url,
        backup_codes=device.backup_codes or [],
    )


# ---------------------------------------------------------------------------
# Enable
# ---------------------------------------------------------------------------

@router.post("/enable")
def enable_2fa(
    body: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify a TOTP code and activate 2FA for the current user."""
    device = (
        db.query(TOTPDevice)
        .filter(TOTPDevice.user_id == current_user.id)
        .first()
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No TOTP device found. Call POST /2fa/setup first.",
        )
    if device.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="2FA is already enabled.",
        )

    try:
        secret = TwoFactorService.get_device_secret(device)
        valid = TwoFactorService.verify_totp(secret, body.code)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code.",
        )

    TwoFactorService.enable_device(device, db)
    return {"detail": "Two-factor authentication enabled successfully."}


# ---------------------------------------------------------------------------
# Disable
# ---------------------------------------------------------------------------

@router.post("/disable")
def disable_2fa(
    body: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify a TOTP code (or backup code) and deactivate 2FA."""
    device = (
        db.query(TOTPDevice)
        .filter(TOTPDevice.user_id == current_user.id)
        .first()
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="2FA is not configured for this account.",
        )
    if not device.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="2FA is already disabled.",
        )

    # Accept a valid TOTP code OR an unused backup code
    code_ok = False
    try:
        secret = TwoFactorService.get_device_secret(device)
        code_ok = TwoFactorService.verify_totp(secret, body.code)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )

    if not code_ok:
        code_ok = TwoFactorService.verify_backup_code(device, body.code)

    if not code_ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code.",
        )

    TwoFactorService.disable_device(device, db)
    return {"detail": "Two-factor authentication disabled."}


# ---------------------------------------------------------------------------
# Verify (standalone — for elevated actions, not login)
# ---------------------------------------------------------------------------

@router.post("/verify")
def verify_2fa(
    body: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify a TOTP code or backup code for the authenticated user.

    This is a general-purpose verification endpoint (e.g. before a sensitive
    action).  It is NOT part of the login flow — see POST /auth/login/2fa.
    """
    device = (
        db.query(TOTPDevice)
        .filter(TOTPDevice.user_id == current_user.id, TOTPDevice.is_enabled == True)  # noqa: E712
        .first()
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="2FA is not enabled for this account.",
        )

    try:
        secret = TwoFactorService.get_device_secret(device)
        code_ok = TwoFactorService.verify_totp(secret, body.code)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )

    if not code_ok:
        # Try backup code
        if TwoFactorService.verify_backup_code(device, body.code):
            TwoFactorService.use_backup_code(device, body.code, db)
            return {"detail": "Backup code accepted.", "backup_code_used": True}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code.",
        )

    return {"detail": "Code verified.", "backup_code_used": False}


# ---------------------------------------------------------------------------
# Backup codes
# ---------------------------------------------------------------------------

@router.get("/backup-codes", response_model=BackupCodesResponse)
def get_backup_codes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return masked backup codes (first 2 chars visible, rest hidden)."""
    device = (
        db.query(TOTPDevice)
        .filter(TOTPDevice.user_id == current_user.id)
        .first()
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="2FA is not configured for this account.",
        )

    masked = TwoFactorService.mask_backup_codes(
        device.backup_codes or [], device.used_backup_codes or []
    )
    return BackupCodesResponse(
        backup_codes=masked,
        used_count=len(device.used_backup_codes or []),
        total=len(device.backup_codes or []),
    )


@router.post("/backup-codes/regenerate")
def regenerate_backup_codes(
    body: TOTPVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify a TOTP code and generate a fresh set of backup codes.

    Old backup codes are invalidated immediately.
    """
    device = (
        db.query(TOTPDevice)
        .filter(TOTPDevice.user_id == current_user.id, TOTPDevice.is_enabled == True)  # noqa: E712
        .first()
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="2FA is not enabled for this account.",
        )

    try:
        secret = TwoFactorService.get_device_secret(device)
        valid = TwoFactorService.verify_totp(secret, body.code)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )

    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid TOTP code.",
        )

    new_codes = TwoFactorService.regenerate_backup_codes(device, db)
    return {
        "detail": "Backup codes regenerated. Save them somewhere safe!",
        "backup_codes": new_codes,
    }
