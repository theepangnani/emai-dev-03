"""
Profile management endpoints: BYOK AI key management (#578).

Routes:
    GET    /api/profile/ai-key    — check whether a key is stored
    PUT    /api/profile/ai-key    — save / replace encrypted key
    DELETE /api/profile/ai-key    — remove stored key
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.encryption import encrypt_key, decrypt_key
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["Profile"])


class AIKeyRequest(BaseModel):
    api_key: str


class AIKeyStatusResponse(BaseModel):
    has_key: bool
    key_preview: str | None  # e.g. "sk-...****" or null


@router.get("/ai-key", response_model=AIKeyStatusResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_ai_key_status(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Return whether the user has a stored AI key and a masked preview."""
    if not current_user.ai_api_key_encrypted:
        return AIKeyStatusResponse(has_key=False, key_preview=None)

    # Decrypt only to build the preview — never log the result
    try:
        plaintext = decrypt_key(current_user.ai_api_key_encrypted)
        if len(plaintext) > 8:
            preview = plaintext[:6] + "..." + plaintext[-4:]
        else:
            preview = plaintext[:3] + "****"
    except Exception:
        # Corrupted ciphertext — treat as no key
        return AIKeyStatusResponse(has_key=False, key_preview=None)

    return AIKeyStatusResponse(has_key=True, key_preview=preview)


@router.put("/ai-key", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def set_ai_key(
    request: Request,
    body: AIKeyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Encrypt and store the user's personal AI API key."""
    key = body.api_key.strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="api_key must not be empty",
        )
    if not key.startswith("sk-"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="API key must start with 'sk-'",
        )

    current_user.ai_api_key_encrypted = encrypt_key(key)
    db.commit()
    # 204 — no body


@router.delete("/ai-key", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def delete_ai_key(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove the user's stored AI API key so the platform key is used instead."""
    current_user.ai_api_key_encrypted = None
    db.commit()
    # 204 — no body
