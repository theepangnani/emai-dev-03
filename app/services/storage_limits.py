"""Storage limit enforcement (#1007)."""
import logging
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.user import User

logger = logging.getLogger(__name__)


def check_upload_allowed(user: User, file_size: int) -> None:
    upload_limit = user.upload_limit_bytes or 10485760
    storage_limit = user.storage_limit_bytes or 104857600
    storage_used = user.storage_used_bytes or 0
    if file_size > upload_limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size ({_fmt(file_size)}) exceeds per-file limit ({_fmt(upload_limit)}).",
        )
    if storage_used + file_size > storage_limit:
        remaining = max(0, storage_limit - storage_used)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload would exceed storage quota. Used: {_fmt(storage_used)}, Limit: {_fmt(storage_limit)}, Remaining: {_fmt(remaining)}.",
        )


def record_upload(db: Session, user: User, file_size: int) -> None:
    user.storage_used_bytes = (user.storage_used_bytes or 0) + file_size
    db.add(user)


def record_deletion(db: Session, user: User, file_size: int) -> None:
    user.storage_used_bytes = max(0, (user.storage_used_bytes or 0) - file_size)
    db.add(user)


def get_storage_info(user: User) -> dict:
    used = user.storage_used_bytes or 0
    limit = user.storage_limit_bytes or 104857600
    upload_limit = user.upload_limit_bytes or 10485760
    pct = (used / limit * 100) if limit > 0 else 0
    return {
        "storage_used_bytes": used,
        "storage_limit_bytes": limit,
        "upload_limit_bytes": upload_limit,
        "storage_used_pct": round(pct, 1),
        "warning": pct >= 80,
        "critical": pct >= 90,
    }


def _fmt(b: int) -> str:
    if b >= 1073741824:
        return f"{b / 1073741824:.1f} GB"
    if b >= 1048576:
        return f"{b / 1048576:.1f} MB"
    if b >= 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b} B"
