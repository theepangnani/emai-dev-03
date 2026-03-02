"""
Storage API routes (#572).

GET /api/storage/files/{key:path}  — serve a stored file (auth + ownership required)
GET /api/storage/usage             — current user's storage usage
GET /api/storage/quota             — current user's quota limits
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.stored_document import StoredDocument
from app.models.user import User
from app.services.storage import get_storage_service, FileStorageService

import io

router = APIRouter(prefix="/storage", tags=["Storage"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_quota_bytes(user: User) -> int:
    tier = getattr(user, "subscription_tier", "free") or "free"
    if tier == "premium":
        return FileStorageService.QUOTA_PREMIUM
    return FileStorageService.QUOTA_FREE


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/files/{key:path}")
def serve_file(
    key: str,
    current_user: User = Depends(get_current_user),
    _db: Session = Depends(get_db),
):
    """Serve a stored file. Auth required; ownership enforced by key prefix."""
    # Ownership check: key must start with users/{current_user.id}/
    expected_prefix = f"users/{current_user.id}/"
    if not key.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="Access denied")

    storage = get_storage_service()
    try:
        data = storage.get_file(key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception:
        raise HTTPException(status_code=404, detail="File not found")

    # Determine content type from the key extension
    import mimetypes
    content_type, _ = mimetypes.guess_type(key)
    content_type = content_type or "application/octet-stream"

    # Extract filename from key for Content-Disposition
    filename = key.split("/")[-1]

    return StreamingResponse(
        io.BytesIO(data),
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )


@router.get("/usage")
def get_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current user's storage usage."""
    # Sum size_bytes from non-deleted StoredDocument records
    docs = (
        db.query(StoredDocument)
        .filter(
            StoredDocument.user_id == current_user.id,
            StoredDocument.is_deleted.is_(False),
        )
        .all()
    )

    used_bytes = sum(d.size_bytes for d in docs)
    quota_bytes = _get_quota_bytes(current_user)
    used_mb = round(used_bytes / (1024 * 1024), 2)
    quota_mb = round(quota_bytes / (1024 * 1024), 2)
    usage_percent = round((used_bytes / quota_bytes) * 100, 1) if quota_bytes > 0 else 0.0

    return {
        "used_bytes": used_bytes,
        "used_mb": used_mb,
        "quota_bytes": quota_bytes,
        "quota_mb": quota_mb,
        "usage_percent": usage_percent,
    }


@router.get("/quota")
def get_quota(
    current_user: User = Depends(get_current_user),
):
    """Return quota limits for the user's subscription tier."""
    tier = getattr(current_user, "subscription_tier", "free") or "free"
    quota_bytes = _get_quota_bytes(current_user)
    quota_mb = round(quota_bytes / (1024 * 1024), 2)

    return {
        "tier": tier,
        "quota_bytes": quota_bytes,
        "quota_mb": quota_mb,
        "quota_gb": round(quota_bytes / (1024 * 1024 * 1024), 2),
        "max_file_size_bytes": FileStorageService.MAX_FILE_SIZE,
        "max_file_size_mb": FileStorageService.MAX_FILE_SIZE // (1024 * 1024),
    }
