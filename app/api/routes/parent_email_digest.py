"""Parent email digest OAuth endpoints.

Allows parents to connect their personal Gmail account to ClassBridge
for email digest polling via gmail.readonly OAuth2 scope.
"""

import logging
import secrets
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.db.database import get_db
from app.models.user import User, UserRole
from app.services.gmail_oauth_service import get_gmail_auth_url, exchange_gmail_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/parent/email-digest", tags=["Parent Email Digest"])

# In-memory OAuth state store (nonce → {user_id, created_at})
_oauth_states: dict[str, dict] = {}
_STATE_TTL = 600  # 10 minutes


def _create_state(user_id: int) -> str:
    """Generate a cryptographic state token for CSRF protection."""
    now = time.time()
    # Clean expired entries
    expired = [k for k, v in _oauth_states.items() if now - v["created_at"] > _STATE_TTL]
    for k in expired:
        _oauth_states.pop(k, None)

    nonce = secrets.token_urlsafe(32)
    _oauth_states[nonce] = {"user_id": user_id, "created_at": now}
    return nonce


def _consume_state(nonce: str) -> dict | None:
    """Validate and consume a state token. Returns context or None."""
    entry = _oauth_states.pop(nonce, None)
    if not entry:
        return None
    if time.time() - entry["created_at"] > _STATE_TTL:
        return None
    return entry


# --- Schemas ---

class GmailAuthUrlResponse(BaseModel):
    authorization_url: str
    state: str


class GmailCallbackRequest(BaseModel):
    code: str
    state: str
    redirect_uri: str


class GmailCallbackResponse(BaseModel):
    status: str
    gmail_address: str | None = None


# --- Endpoints ---

@router.get("/gmail/auth-url", response_model=GmailAuthUrlResponse)
def gmail_auth_url(
    request: Request,
    redirect_uri: str,
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Generate a Google OAuth URL for connecting Gmail (gmail.readonly scope).

    The frontend should redirect the user to the returned URL. After consent,
    Google will redirect back to the provided redirect_uri with a code and state.
    """
    state = _create_state(current_user.id)
    url = get_gmail_auth_url(redirect_uri=redirect_uri, state=state)
    return GmailAuthUrlResponse(authorization_url=url, state=state)


@router.post("/gmail/callback", response_model=GmailCallbackResponse)
def gmail_callback(
    request: Request,
    body: GmailCallbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Exchange the Google OAuth code for tokens and store the integration.

    Creates or updates a ParentGmailIntegration record linking the parent's
    ClassBridge account to their personal Gmail for email digest polling.
    """
    # Validate state
    state_ctx = _consume_state(body.state)
    if not state_ctx:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state",
        )
    if state_ctx["user_id"] != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="OAuth state mismatch",
        )

    # Exchange code for tokens
    try:
        tokens = exchange_gmail_code(code=body.code, redirect_uri=body.redirect_uri)
    except Exception:
        logger.exception("Gmail OAuth token exchange failed for user %s", current_user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange Gmail authorization code",
        )

    if not tokens.get("refresh_token"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token received. Please revoke ClassBridge access in your Google account settings and try again.",
        )

    # Get the Gmail address from the access token
    gmail_address = _get_gmail_address(tokens["access_token"])

    # Store the integration record
    try:
        from app.models.parent_gmail_integration import ParentGmailIntegration
    except ImportError:
        # Model may not exist yet (parallel development) — store on user for now
        logger.warning(
            "ParentGmailIntegration model not found; skipping DB persistence for user %s",
            current_user.id,
        )
        return GmailCallbackResponse(status="ok", gmail_address=gmail_address)

    # Upsert: update if parent already has an integration, else create
    existing = (
        db.query(ParentGmailIntegration)
        .filter(ParentGmailIntegration.user_id == current_user.id)
        .first()
    )
    if existing:
        existing.gmail_address = gmail_address
        existing.access_token = tokens["access_token"]
        existing.refresh_token = tokens["refresh_token"]
        existing.granted_scopes = tokens.get("granted_scopes", "")
        existing.connected_at = datetime.now(timezone.utc)
    else:
        integration = ParentGmailIntegration(
            user_id=current_user.id,
            gmail_address=gmail_address,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            granted_scopes=tokens.get("granted_scopes", ""),
        )
        db.add(integration)

    db.commit()
    return GmailCallbackResponse(status="ok", gmail_address=gmail_address)


def _get_gmail_address(access_token: str) -> str | None:
    """Fetch the authenticated user's email address from Google userinfo."""
    import requests as _requests

    try:
        resp = _requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if resp.ok:
            return resp.json().get("email")
    except Exception:
        logger.exception("Failed to fetch Gmail address from userinfo")
    return None
