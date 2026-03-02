"""LMS Connections API routes — Multi-LMS Provider Framework (#22, #23, #27, #28).

Routes:
  GET    /api/lms/providers                  — list available providers
  GET    /api/lms/institutions               — list institutions (filterable by provider)
  POST   /api/lms/institutions               — create institution (admin only)
  GET    /api/lms/connections                — list user's connections
  POST   /api/lms/connections                — create/register a connection
  PATCH  /api/lms/connections/{id}           — update label or status
  DELETE /api/lms/connections/{id}           — remove connection
  GET    /api/lms/connections/{id}/status    — sync status for a connection
  POST   /api/lms/connections/{id}/sync      — sync a single connection (owner only)

Moodle token-based connect flow:
  GET    /api/lms/moodle/connect             — return token entry instructions
  POST   /api/lms/moodle/connect             — validate token, create LMSConnection
  POST   /api/lms/moodle/{id}/refresh        — re-validate token, update connection

Admin routes:
  GET    /api/admin/lms/institutions              — list all institutions (admin)
  POST   /api/admin/lms/institutions              — create institution (admin)
  PATCH  /api/admin/lms/institutions/{id}         — update institution (admin)
  DELETE /api/admin/lms/institutions/{id}         — deactivate institution (admin, soft-delete)
  GET    /api/admin/lms/institutions/{id}/connections — connections for an institution (admin)
  GET    /api/admin/lms/stats                     — connection counts by provider + institution
  POST   /api/admin/lms/sync/trigger              — manually trigger full sync (admin)
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.lms_institution import LMSInstitution
from app.models.lms_connection import LMSConnection
from app.services.lms_registry import list_providers, get_provider
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lms", tags=["LMS Connections"])


# ---------------------------------------------------------------------------
# Ontario Brightspace institutions seed data
# ---------------------------------------------------------------------------

_ONTARIO_BRIGHTSPACE_SEED = [
    {
        "name": "TDSB — Toronto District School Board",
        "provider": "brightspace",
        "base_url": "https://tdsb.brightspace.com",
        "region": "ON",
    },
    {
        "name": "PDSB — Peel District School Board",
        "provider": "brightspace",
        "base_url": "https://peel.brightspace.com",
        "region": "ON",
    },
    {
        "name": "YRDSB — York Region District School Board",
        "provider": "brightspace",
        "base_url": "https://yrdsb.brightspace.com",
        "region": "ON",
    },
    {
        "name": "HDSB — Halton District School Board",
        "provider": "brightspace",
        "base_url": "https://hdsb.brightspace.com",
        "region": "ON",
    },
    {
        "name": "OCDSB — Ottawa-Carleton District School Board",
        "provider": "brightspace",
        "base_url": "https://ocdsb.brightspace.com",
        "region": "ON",
    },
]


def _seed_institutions(db: Session) -> None:
    """Idempotently seed the 5 Ontario Brightspace institutions."""
    count = db.query(LMSInstitution).count()
    if count > 0:
        return
    for data in _ONTARIO_BRIGHTSPACE_SEED:
        inst = LMSInstitution(**data, is_active=True)
        db.add(inst)
    db.commit()
    logger.info("Seeded %d Ontario Brightspace institutions", len(_ONTARIO_BRIGHTSPACE_SEED))


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class InstitutionCreate(BaseModel):
    name: str
    provider: str
    base_url: Optional[str] = None
    region: Optional[str] = None
    is_active: bool = True
    metadata_json: Optional[str] = None


class InstitutionOut(BaseModel):
    id: int
    name: str
    provider: str
    base_url: Optional[str]
    region: Optional[str]
    is_active: bool
    metadata_json: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ConnectionCreate(BaseModel):
    provider: str
    institution_id: Optional[int] = None
    label: Optional[str] = None


class ConnectionUpdate(BaseModel):
    label: Optional[str] = None
    status: Optional[str] = None


class ConnectionOut(BaseModel):
    id: int
    user_id: int
    institution_id: Optional[int]
    provider: str
    label: Optional[str]
    status: str
    last_sync_at: Optional[datetime]
    sync_error: Optional[str]
    courses_synced: int
    external_user_id: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    # Nested institution info (if present)
    institution_name: Optional[str] = None
    institution_base_url: Optional[str] = None

    model_config = {"from_attributes": True}


class ConnectionStatusOut(BaseModel):
    id: int
    provider: str
    status: str
    last_sync_at: Optional[datetime]
    sync_error: Optional[str]
    courses_synced: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _connection_out(conn: LMSConnection) -> ConnectionOut:
    """Serialize an LMSConnection including denormalized institution fields."""
    inst_name = None
    inst_url = None
    if conn.institution:
        inst_name = conn.institution.name
        inst_url = conn.institution.base_url
    return ConnectionOut(
        id=conn.id,
        user_id=conn.user_id,
        institution_id=conn.institution_id,
        provider=conn.provider,
        label=conn.label,
        status=conn.status,
        last_sync_at=conn.last_sync_at,
        sync_error=conn.sync_error,
        courses_synced=conn.courses_synced,
        external_user_id=conn.external_user_id,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
        institution_name=inst_name,
        institution_base_url=inst_url,
    )


VALID_STATUSES = {"connected", "expired", "error", "disconnected", "stale"}
VALID_PROVIDERS = {"google_classroom", "brightspace", "canvas", "moodle"}


# ---------------------------------------------------------------------------
# Provider discovery
# ---------------------------------------------------------------------------


@router.get("/providers", summary="List all registered LMS providers")
def get_providers(
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """Return metadata for all providers registered in the LMS registry."""
    return list_providers()


# ---------------------------------------------------------------------------
# Institutions
# ---------------------------------------------------------------------------


@router.get("/institutions", response_model=list[InstitutionOut], summary="List institutions")
def get_institutions(
    provider: Optional[str] = Query(None, description="Filter by provider string"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[InstitutionOut]:
    """List all LMS institutions.  Optionally filter by provider.
    Auto-seeds 5 Ontario Brightspace institutions if the table is empty.
    """
    _seed_institutions(db)

    q = db.query(LMSInstitution).filter(LMSInstitution.is_active.is_(True))
    if provider:
        q = q.filter(LMSInstitution.provider == provider)
    return q.order_by(LMSInstitution.name).all()


@router.post(
    "/institutions",
    response_model=InstitutionOut,
    status_code=201,
    summary="Create institution (admin only)",
)
def create_institution(
    body: InstitutionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> InstitutionOut:
    """Create a new LMS institution record.  Admin-only."""
    if body.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown provider '{body.provider}'. Valid: {sorted(VALID_PROVIDERS)}",
        )
    inst = LMSInstitution(
        name=body.name,
        provider=body.provider,
        base_url=body.base_url,
        region=body.region,
        is_active=body.is_active,
        metadata_json=body.metadata_json,
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    logger.info("Admin %s created LMS institution: %s", current_user.id, inst.name)
    return inst


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


@router.get("/connections", response_model=list[ConnectionOut], summary="List user's connections")
def list_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConnectionOut]:
    """Return all LMS connections owned by the authenticated user."""
    connections = (
        db.query(LMSConnection)
        .filter(LMSConnection.user_id == current_user.id)
        .order_by(LMSConnection.created_at)
        .all()
    )
    return [_connection_out(c) for c in connections]


@router.post(
    "/connections",
    response_model=ConnectionOut,
    status_code=201,
    summary="Create/register an LMS connection",
)
def create_connection(
    body: ConnectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionOut:
    """Register a new LMS connection for the current user.

    For Google Classroom the connection is created with status="connected"
    (the existing /api/google/* OAuth flow already handles token storage).

    For all other providers the connection is created with status="disconnected"
    because OAuth is not yet implemented for those providers.
    """
    if body.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown provider '{body.provider}'. Valid: {sorted(VALID_PROVIDERS)}",
        )

    provider_adapter = get_provider(body.provider)
    if not provider_adapter:
        raise HTTPException(status_code=422, detail=f"Provider '{body.provider}' is not registered.")

    # Validate institution_id if provided
    if body.institution_id is not None:
        inst = db.query(LMSInstitution).filter(LMSInstitution.id == body.institution_id).first()
        if not inst:
            raise HTTPException(status_code=404, detail="Institution not found.")

    # Determine initial status
    # Google Classroom: existing OAuth already grants access → connected
    # Others: OAuth not implemented yet → disconnected
    initial_status = "connected" if body.provider == "google_classroom" else "disconnected"

    conn = LMSConnection(
        user_id=current_user.id,
        institution_id=body.institution_id,
        provider=body.provider,
        label=body.label,
        status=initial_status,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)

    logger.info(
        "User %s created LMS connection: provider=%s institution_id=%s status=%s",
        current_user.id,
        body.provider,
        body.institution_id,
        initial_status,
    )
    return _connection_out(conn)


@router.patch(
    "/connections/{connection_id}",
    response_model=ConnectionOut,
    summary="Update connection label or status",
)
def update_connection(
    connection_id: int,
    body: ConnectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionOut:
    """Update a connection's label or status.  Users can only modify their own connections."""
    conn = db.query(LMSConnection).filter(LMSConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found.")

    # Ownership check (admins can manage any connection)
    is_admin = current_user.roles and "admin" in current_user.roles
    if conn.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to modify this connection.")

    if body.label is not None:
        conn.label = body.label
    if body.status is not None:
        if body.status not in VALID_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status '{body.status}'. Valid: {sorted(VALID_STATUSES)}",
            )
        conn.status = body.status
    conn.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(conn)
    return _connection_out(conn)


@router.delete(
    "/connections/{connection_id}",
    status_code=204,
    summary="Remove an LMS connection",
)
def delete_connection(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Permanently remove an LMS connection.  Tokens are deleted."""
    conn = db.query(LMSConnection).filter(LMSConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found.")

    is_admin = current_user.roles and "admin" in current_user.roles
    if conn.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this connection.")

    db.delete(conn)
    db.commit()
    logger.info("User %s deleted LMS connection %s", current_user.id, connection_id)


@router.get(
    "/connections/{connection_id}/status",
    response_model=ConnectionStatusOut,
    summary="Get sync status for a connection",
)
def get_connection_status(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionStatusOut:
    """Return the sync status for a specific connection."""
    conn = db.query(LMSConnection).filter(LMSConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found.")

    is_admin = current_user.roles and "admin" in current_user.roles
    if conn.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to view this connection.")

    return conn  # type: ignore[return-value]


@router.post(
    "/connections/{connection_id}/sync",
    response_model=ConnectionStatusOut,
    summary="Sync a single LMS connection (owner only)",
)
async def sync_single_connection_endpoint(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionStatusOut:
    """Trigger an immediate sync for one of the current user's connections."""
    conn = db.query(LMSConnection).filter(LMSConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found.")

    is_admin = current_user.roles and "admin" in current_user.roles
    if conn.user_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to sync this connection.")

    from app.jobs.lms_sync import sync_single_connection
    try:
        await sync_single_connection(conn, db)
    except Exception as exc:
        logger.error("Manual sync failed for connection %s: %s", connection_id, exc)
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}") from exc

    db.refresh(conn)
    return conn  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Brightspace OAuth2 flow  (#24)
# ---------------------------------------------------------------------------

# In-memory state store: state_token → {"user_id": int, "institution_id": int}
# In production this should be replaced with a short-TTL cache (e.g. Redis).
_brightspace_oauth_state: dict[str, dict] = {}


@router.get(
    "/brightspace/connect",
    summary="Initiate Brightspace OAuth2 Authorization Code flow",
    response_class=RedirectResponse,
)
async def brightspace_connect(
    institution_id: int = Query(..., description="LMSInstitution ID to connect to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """Redirect the authenticated user to their institution's Brightspace OAuth
    consent page.

    The institution must exist, be active, and have provider="brightspace".
    OAuth credentials (client_id, client_secret) must be stored in the
    institution's metadata_json field as {"client_id": "...", "client_secret": "..."}.

    After the user grants consent, Brightspace redirects to /api/lms/brightspace/callback.
    """
    inst = db.query(LMSInstitution).filter(LMSInstitution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found.")
    if inst.provider != "brightspace":
        raise HTTPException(
            status_code=422,
            detail=f"Institution {institution_id} is not a Brightspace institution.",
        )
    if not inst.is_active:
        raise HTTPException(status_code=422, detail="Institution is not active.")

    state = secrets.token_urlsafe(32)
    _brightspace_oauth_state[state] = {
        "user_id": current_user.id,
        "institution_id": institution_id,
    }

    redirect_uri = f"{settings.frontend_url}/api/lms/brightspace/callback"

    from app.services.brightspace import BrightspaceOAuthClient
    oauth = BrightspaceOAuthClient()
    auth_url = oauth.generate_auth_url(institution=inst, redirect_uri=redirect_uri, state=state)

    logger.info(
        "User %s initiating Brightspace OAuth for institution %s",
        current_user.id,
        institution_id,
    )
    return RedirectResponse(url=auth_url, status_code=302)


@router.get(
    "/brightspace/callback",
    response_model=ConnectionOut,
    summary="Handle Brightspace OAuth2 callback — exchange code for tokens",
)
async def brightspace_callback(
    code: str = Query(..., description="Authorization code from Brightspace"),
    state: str = Query(..., description="CSRF state token"),
    db: Session = Depends(get_db),
) -> ConnectionOut:
    """Exchange the authorization code for tokens and create (or update) an
    LMSConnection record for the user.

    The state parameter is validated against the in-memory store populated by
    the /connect endpoint.  On success the connection status is set to
    "connected" and tokens are stored.

    Note: This endpoint does NOT require a JWT because the user arrives here
    via a browser redirect from Brightspace.  Identity is established via the
    state token which was associated with a user_id during /connect.
    """
    state_data = _brightspace_oauth_state.pop(state, None)
    if not state_data:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state token.  Please restart the connection flow.",
        )

    user_id: int = state_data["user_id"]
    institution_id: int = state_data["institution_id"]

    inst = db.query(LMSInstitution).filter(LMSInstitution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found.")

    redirect_uri = f"{settings.frontend_url}/api/lms/brightspace/callback"

    from app.services.brightspace import BrightspaceOAuthClient
    oauth = BrightspaceOAuthClient()
    try:
        tokens = await oauth.exchange_code(
            institution=inst,
            code=code,
            redirect_uri=redirect_uri,
        )
    except Exception as exc:
        logger.error(
            "Brightspace token exchange failed for user %s institution %s: %s",
            user_id,
            institution_id,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to exchange authorization code: {exc}",
        ) from exc

    # Upsert LMSConnection
    conn = (
        db.query(LMSConnection)
        .filter(
            LMSConnection.user_id == user_id,
            LMSConnection.institution_id == institution_id,
            LMSConnection.provider == "brightspace",
        )
        .first()
    )

    expires_in_seconds: int = tokens.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

    if conn is None:
        conn = LMSConnection(
            user_id=user_id,
            institution_id=institution_id,
            provider="brightspace",
            status="connected",
            access_token_enc=tokens.get("access_token", ""),
            refresh_token_enc=tokens.get("refresh_token", ""),
            token_expires_at=expires_at,
        )
        db.add(conn)
        logger.info(
            "Created Brightspace LMSConnection for user %s institution %s",
            user_id,
            institution_id,
        )
    else:
        conn.access_token_enc = tokens.get("access_token", "")
        conn.refresh_token_enc = tokens.get("refresh_token", "")
        conn.token_expires_at = expires_at
        conn.status = "connected"
        conn.sync_error = None
        logger.info(
            "Updated Brightspace LMSConnection %s for user %s",
            conn.id,
            user_id,
        )

    db.commit()
    db.refresh(conn)
    return _connection_out(conn)


@router.post(
    "/brightspace/{connection_id}/refresh",
    response_model=ConnectionOut,
    summary="Refresh Brightspace access token",
)
async def brightspace_refresh_token(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionOut:
    """Use the stored refresh token to obtain a new Brightspace access token.

    Updates the connection record with the new token and expiry, resets
    status to "connected", and clears any previous sync_error.

    Returns the updated connection.
    """
    conn = db.query(LMSConnection).filter(LMSConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found.")

    is_admin = current_user.roles and "admin" in current_user.roles
    if conn.user_id != current_user.id and not is_admin:
        raise HTTPException(
            status_code=403, detail="Not authorized to refresh this connection."
        )

    if conn.provider != "brightspace":
        raise HTTPException(
            status_code=422,
            detail=f"Connection {connection_id} is not a Brightspace connection.",
        )

    if not conn.institution:
        raise HTTPException(
            status_code=422,
            detail="Connection has no associated institution — cannot refresh token.",
        )

    if not conn.refresh_token_enc:
        raise HTTPException(
            status_code=422,
            detail="No refresh token stored.  Please re-authenticate via /connect.",
        )

    from app.services.brightspace import BrightspaceOAuthClient
    oauth = BrightspaceOAuthClient()
    try:
        tokens = await oauth.refresh_access_token(
            institution=conn.institution,
            refresh_token=conn.refresh_token_enc,
        )
    except Exception as exc:
        conn.status = "expired"
        conn.sync_error = str(exc)
        db.commit()
        logger.error(
            "Brightspace token refresh failed for connection %s: %s",
            connection_id,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Token refresh failed: {exc}",
        ) from exc

    expires_in_seconds: int = tokens.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

    conn.access_token_enc = tokens.get("access_token", "")
    conn.refresh_token_enc = tokens.get("refresh_token", conn.refresh_token_enc)
    conn.token_expires_at = expires_at
    conn.status = "connected"
    conn.sync_error = None
    conn.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(conn)

    logger.info("Refreshed Brightspace token for connection %s", connection_id)
    return _connection_out(conn)


# ---------------------------------------------------------------------------
# Canvas OAuth2 flow
# ---------------------------------------------------------------------------

# In-memory state store: state_token → {"user_id": int, "institution_id": int}
# In production this should be replaced with a short-TTL cache (e.g. Redis).
_canvas_oauth_state: dict[str, dict] = {}


@router.get(
    "/canvas/connect",
    summary="Initiate Canvas OAuth2 Authorization Code flow",
    response_class=RedirectResponse,
)
async def canvas_connect(
    institution_id: int = Query(..., description="LMSInstitution ID to connect to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """Redirect the authenticated user to their institution's Canvas OAuth
    consent page.

    The institution must exist, be active, and have provider="canvas".
    OAuth credentials (client_id, client_secret) must be stored in the
    institution's metadata_json field as {"client_id": "...", "client_secret": "..."}.

    After the user grants consent, Canvas redirects to /api/lms/canvas/callback.
    """
    inst = db.query(LMSInstitution).filter(LMSInstitution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found.")
    if inst.provider != "canvas":
        raise HTTPException(
            status_code=422,
            detail=f"Institution {institution_id} is not a Canvas institution.",
        )
    if not inst.is_active:
        raise HTTPException(status_code=422, detail="Institution is not active.")

    state = secrets.token_urlsafe(32)
    _canvas_oauth_state[state] = {
        "user_id": current_user.id,
        "institution_id": institution_id,
    }

    redirect_uri = f"{settings.frontend_url}/api/lms/canvas/callback"

    from app.services.canvas import CanvasOAuthClient
    oauth = CanvasOAuthClient()
    auth_url = oauth.generate_auth_url(institution=inst, redirect_uri=redirect_uri, state=state)

    logger.info(
        "User %s initiating Canvas OAuth for institution %s",
        current_user.id,
        institution_id,
    )
    return RedirectResponse(url=auth_url, status_code=302)


@router.get(
    "/canvas/callback",
    response_model=ConnectionOut,
    summary="Handle Canvas OAuth2 callback — exchange code for tokens",
)
async def canvas_callback(
    code: str = Query(..., description="Authorization code from Canvas"),
    state: str = Query(..., description="CSRF state token"),
    db: Session = Depends(get_db),
) -> ConnectionOut:
    """Exchange the authorization code for tokens and create (or update) an
    LMSConnection record for the user.

    The state parameter is validated against the in-memory store populated by
    the /connect endpoint.  On success the connection status is set to
    "connected" and tokens are stored.

    Note: This endpoint does NOT require a JWT because the user arrives here
    via a browser redirect from Canvas.  Identity is established via the
    state token which was associated with a user_id during /connect.
    """
    state_data = _canvas_oauth_state.pop(state, None)
    if not state_data:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state token.  Please restart the connection flow.",
        )

    user_id: int = state_data["user_id"]
    institution_id: int = state_data["institution_id"]

    inst = db.query(LMSInstitution).filter(LMSInstitution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found.")

    redirect_uri = f"{settings.frontend_url}/api/lms/canvas/callback"

    from app.services.canvas import CanvasOAuthClient
    oauth = CanvasOAuthClient()
    try:
        tokens = await oauth.exchange_code(
            institution=inst,
            code=code,
            redirect_uri=redirect_uri,
        )
    except Exception as exc:
        logger.error(
            "Canvas token exchange failed for user %s institution %s: %s",
            user_id,
            institution_id,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to exchange authorization code: {exc}",
        ) from exc

    # Upsert LMSConnection
    conn = (
        db.query(LMSConnection)
        .filter(
            LMSConnection.user_id == user_id,
            LMSConnection.institution_id == institution_id,
            LMSConnection.provider == "canvas",
        )
        .first()
    )

    expires_in_seconds: int = tokens.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

    if conn is None:
        conn = LMSConnection(
            user_id=user_id,
            institution_id=institution_id,
            provider="canvas",
            status="connected",
            access_token_enc=tokens.get("access_token", ""),
            refresh_token_enc=tokens.get("refresh_token", ""),
            token_expires_at=expires_at,
        )
        db.add(conn)
        logger.info(
            "Created Canvas LMSConnection for user %s institution %s",
            user_id,
            institution_id,
        )
    else:
        conn.access_token_enc = tokens.get("access_token", "")
        conn.refresh_token_enc = tokens.get("refresh_token", "")
        conn.token_expires_at = expires_at
        conn.status = "connected"
        conn.sync_error = None
        logger.info(
            "Updated Canvas LMSConnection %s for user %s",
            conn.id,
            user_id,
        )

    db.commit()
    db.refresh(conn)
    return _connection_out(conn)


@router.post(
    "/canvas/{connection_id}/refresh",
    response_model=ConnectionOut,
    summary="Refresh Canvas access token",
)
async def canvas_refresh_token(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionOut:
    """Use the stored refresh token to obtain a new Canvas access token.

    Updates the connection record with the new token and expiry, resets
    status to "connected", and clears any previous sync_error.

    Returns the updated connection.
    """
    conn = db.query(LMSConnection).filter(LMSConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found.")

    is_admin = current_user.roles and "admin" in current_user.roles
    if conn.user_id != current_user.id and not is_admin:
        raise HTTPException(
            status_code=403, detail="Not authorized to refresh this connection."
        )

    if conn.provider != "canvas":
        raise HTTPException(
            status_code=422,
            detail=f"Connection {connection_id} is not a Canvas connection.",
        )

    if not conn.institution:
        raise HTTPException(
            status_code=422,
            detail="Connection has no associated institution — cannot refresh token.",
        )

    if not conn.refresh_token_enc:
        raise HTTPException(
            status_code=422,
            detail="No refresh token stored.  Please re-authenticate via /connect.",
        )

    from app.services.canvas import CanvasOAuthClient
    oauth = CanvasOAuthClient()
    try:
        tokens = await oauth.refresh_access_token(
            institution=conn.institution,
            refresh_token=conn.refresh_token_enc,
        )
    except Exception as exc:
        conn.status = "expired"
        conn.sync_error = str(exc)
        db.commit()
        logger.error(
            "Canvas token refresh failed for connection %s: %s",
            connection_id,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Token refresh failed: {exc}",
        ) from exc

    expires_in_seconds: int = tokens.get("expires_in", 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

    conn.access_token_enc = tokens.get("access_token", "")
    conn.refresh_token_enc = tokens.get("refresh_token", conn.refresh_token_enc)
    conn.token_expires_at = expires_at
    conn.status = "connected"
    conn.sync_error = None
    conn.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(conn)

    logger.info("Refreshed Canvas token for connection %s", connection_id)
    return _connection_out(conn)


# ---------------------------------------------------------------------------
# Moodle token-based connect flow
# ---------------------------------------------------------------------------


class MoodleConnectBody(BaseModel):
    institution_id: int
    token: str


@router.get(
    "/moodle/connect",
    summary="Get Moodle token entry instructions",
)
async def moodle_connect_info(
    institution_id: int = Query(..., description="LMSInstitution ID to connect to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return token entry instructions for connecting a Moodle instance.

    Moodle does not support OAuth2 Authorization Code flow.  Instead the user
    must generate a Web Service token in their Moodle admin panel and paste it
    into ClassBridge.

    Returns JSON with:
      - institution_id: int
      - connect_url:    str  — URL to Moodle token management page
      - instructions:   str  — human-readable guidance
    """
    inst = db.query(LMSInstitution).filter(LMSInstitution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found.")
    if inst.provider != "moodle":
        raise HTTPException(
            status_code=422,
            detail=f"Institution {institution_id} is not a Moodle institution.",
        )
    if not inst.is_active:
        raise HTTPException(status_code=422, detail="Institution is not active.")

    base_url = (inst.base_url or "").rstrip("/")
    token_page = f"{base_url}/admin/settings.php?section=webservicetokens" if base_url else ""

    logger.info(
        "User %s requested Moodle connect instructions for institution %s",
        current_user.id,
        institution_id,
    )
    return {
        "institution_id": institution_id,
        "connect_url": token_page,
        "instructions": (
            "Enter your Moodle Web Service token below.  "
            "To generate a token, go to your Moodle site "
            "Administration → Plugins → Web services → Manage tokens, "
            "and create a token for the 'moodle_mobile_app' service."
        ),
    }


@router.post(
    "/moodle/connect",
    response_model=ConnectionOut,
    status_code=201,
    summary="Connect Moodle via Web Service token",
)
async def moodle_connect_token(
    body: MoodleConnectBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionOut:
    """Validate a Moodle Web Service token and create (or update) an LMSConnection.

    The token is validated by calling core_webservice_get_site_info on the
    institution's Moodle base URL.  On success the connection is created with
    status="connected" and the token is stored in access_token_enc.

    Args (JSON body):
        institution_id: LMSInstitution.id for the Moodle instance.
        token:          Moodle Web Service token string.

    Returns:
        The created or updated LMSConnection.

    Raises:
        404: Institution not found.
        422: Institution is not Moodle, is inactive, or token is invalid.
    """
    inst = db.query(LMSInstitution).filter(LMSInstitution.id == body.institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found.")
    if inst.provider != "moodle":
        raise HTTPException(
            status_code=422,
            detail=f"Institution {body.institution_id} is not a Moodle institution.",
        )
    if not inst.is_active:
        raise HTTPException(status_code=422, detail="Institution is not active.")

    if not body.token or not body.token.strip():
        raise HTTPException(status_code=422, detail="Token must not be empty.")

    base_url = (inst.base_url or "").rstrip("/")
    if not base_url:
        raise HTTPException(
            status_code=422,
            detail="Institution has no base_url configured.",
        )

    # Validate the token against Moodle
    from app.services.moodle import MoodleAPIClient
    client = MoodleAPIClient(base_url=base_url, token=body.token.strip())
    try:
        site_info = await client.get_site_info()
    except Exception as exc:
        logger.warning(
            "Moodle token validation failed for user %s institution %s: %s",
            current_user.id,
            body.institution_id,
            exc,
        )
        raise HTTPException(
            status_code=422,
            detail=f"Moodle token validation failed: {exc}",
        ) from exc

    if not site_info or "exception" in site_info:
        raise HTTPException(
            status_code=422,
            detail="Moodle rejected the token.  Please check the token and try again.",
        )

    external_user_id = str(site_info.get("userid", ""))

    # Upsert LMSConnection
    conn = (
        db.query(LMSConnection)
        .filter(
            LMSConnection.user_id == current_user.id,
            LMSConnection.institution_id == body.institution_id,
            LMSConnection.provider == "moodle",
        )
        .first()
    )

    if conn is None:
        conn = LMSConnection(
            user_id=current_user.id,
            institution_id=body.institution_id,
            provider="moodle",
            status="connected",
            access_token_enc=body.token.strip(),
            external_user_id=external_user_id or None,
        )
        db.add(conn)
        logger.info(
            "Created Moodle LMSConnection for user %s institution %s (userid=%s)",
            current_user.id,
            body.institution_id,
            external_user_id,
        )
    else:
        conn.access_token_enc = body.token.strip()
        conn.status = "connected"
        conn.sync_error = None
        conn.external_user_id = external_user_id or conn.external_user_id
        conn.updated_at = datetime.now(timezone.utc)
        logger.info(
            "Updated Moodle LMSConnection %s for user %s (userid=%s)",
            conn.id,
            current_user.id,
            external_user_id,
        )

    db.commit()
    db.refresh(conn)
    return _connection_out(conn)


@router.post(
    "/moodle/{connection_id}/refresh",
    response_model=ConnectionOut,
    summary="Re-validate Moodle token and update connection",
)
async def moodle_refresh_token(
    connection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionOut:
    """Re-validate the stored Moodle token and update last_synced_at.

    Since Moodle tokens do not expire (unless manually revoked), this endpoint
    re-validates the existing token by calling core_webservice_get_site_info.
    On success it resets status to "connected" and clears any sync_error.

    Returns:
        The updated LMSConnection.

    Raises:
        404: Connection not found.
        403: Not authorized to refresh this connection.
        422: Connection is not Moodle, or has no token stored.
        502: Moodle token re-validation failed (token may have been revoked).
    """
    conn = db.query(LMSConnection).filter(LMSConnection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found.")

    is_admin = current_user.roles and "admin" in current_user.roles
    if conn.user_id != current_user.id and not is_admin:
        raise HTTPException(
            status_code=403, detail="Not authorized to refresh this connection."
        )

    if conn.provider != "moodle":
        raise HTTPException(
            status_code=422,
            detail=f"Connection {connection_id} is not a Moodle connection.",
        )

    if not conn.institution:
        raise HTTPException(
            status_code=422,
            detail="Connection has no associated institution — cannot re-validate token.",
        )

    if not conn.access_token_enc:
        raise HTTPException(
            status_code=422,
            detail="No token stored.  Please re-connect via /moodle/connect.",
        )

    base_url = (conn.institution.base_url or "").rstrip("/")
    if not base_url:
        raise HTTPException(
            status_code=422,
            detail="Institution has no base_url configured.",
        )

    from app.services.moodle import MoodleAPIClient
    client = MoodleAPIClient(base_url=base_url, token=conn.access_token_enc)
    try:
        site_info = await client.get_site_info()
    except Exception as exc:
        conn.status = "expired"
        conn.sync_error = str(exc)
        db.commit()
        logger.error(
            "Moodle token re-validation failed for connection %s: %s",
            connection_id,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Moodle token re-validation failed: {exc}",
        ) from exc

    if not site_info or "exception" in site_info:
        conn.status = "expired"
        conn.sync_error = "Token rejected by Moodle."
        db.commit()
        raise HTTPException(
            status_code=422,
            detail="Moodle rejected the token.  Please re-connect with a new token.",
        )

    conn.status = "connected"
    conn.sync_error = None
    conn.last_sync_at = datetime.now(timezone.utc)
    conn.updated_at = datetime.now(timezone.utc)
    external_user_id = str(site_info.get("userid", ""))
    if external_user_id:
        conn.external_user_id = external_user_id

    db.commit()
    db.refresh(conn)

    logger.info("Re-validated Moodle token for connection %s", connection_id)
    return _connection_out(conn)


# ---------------------------------------------------------------------------
# Admin router — all routes under /admin/lms
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/admin/lms", tags=["Admin — LMS Management"])


# --- Pydantic schemas for admin operations ---


class InstitutionUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    region: Optional[str] = None
    is_active: Optional[bool] = None
    metadata_json: Optional[str] = None


class AdminConnectionOut(BaseModel):
    """Richer connection view for admin lists (includes user email)."""
    id: int
    user_id: int
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    institution_id: Optional[int]
    provider: str
    label: Optional[str]
    status: str
    last_sync_at: Optional[datetime]
    sync_error: Optional[str]
    courses_synced: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class LMSStatsOut(BaseModel):
    total_connections: int
    by_provider: dict[str, dict[str, int]]
    by_institution: list[dict[str, Any]]
    last_sync_summary: dict[str, int]


class SyncTriggerOut(BaseModel):
    synced: int
    errors: int
    message: str


# --- Helpers ---


def _admin_conn_out(conn: LMSConnection) -> AdminConnectionOut:
    user = conn.user
    return AdminConnectionOut(
        id=conn.id,
        user_id=conn.user_id,
        user_email=user.email if user else None,
        user_name=user.full_name if user else None,
        institution_id=conn.institution_id,
        provider=conn.provider,
        label=conn.label,
        status=conn.status,
        last_sync_at=conn.last_sync_at,
        sync_error=conn.sync_error,
        courses_synced=conn.courses_synced,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


# --- Admin institution CRUD ---


@admin_router.get(
    "/institutions",
    response_model=list[InstitutionOut],
    summary="List all institutions (admin)",
)
def admin_list_institutions(
    provider: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> list[InstitutionOut]:
    """Return all LMS institutions including inactive ones (admin view)."""
    q = db.query(LMSInstitution)
    if not include_inactive:
        q = q.filter(LMSInstitution.is_active.is_(True))
    if provider:
        q = q.filter(LMSInstitution.provider == provider)
    return q.order_by(LMSInstitution.name).all()


@admin_router.post(
    "/institutions",
    response_model=InstitutionOut,
    status_code=201,
    summary="Create institution (admin)",
)
def admin_create_institution(
    body: InstitutionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> InstitutionOut:
    """Create a new LMS institution record.  Admin-only."""
    if body.provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown provider '{body.provider}'. Valid: {sorted(VALID_PROVIDERS)}",
        )
    inst = LMSInstitution(
        name=body.name,
        provider=body.provider,
        base_url=body.base_url,
        region=body.region,
        is_active=body.is_active,
        metadata_json=body.metadata_json,
    )
    db.add(inst)
    db.commit()
    db.refresh(inst)
    logger.info("Admin %s created LMS institution: %s", current_user.id, inst.name)
    return inst


@admin_router.patch(
    "/institutions/{institution_id}",
    response_model=InstitutionOut,
    summary="Update institution (admin)",
)
def admin_update_institution(
    institution_id: int,
    body: InstitutionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> InstitutionOut:
    """Partially update an LMS institution.  Admin-only."""
    inst = db.query(LMSInstitution).filter(LMSInstitution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found.")

    if body.name is not None:
        inst.name = body.name
    if body.provider is not None:
        if body.provider not in VALID_PROVIDERS:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown provider '{body.provider}'. Valid: {sorted(VALID_PROVIDERS)}",
            )
        inst.provider = body.provider
    if body.base_url is not None:
        inst.base_url = body.base_url
    if body.region is not None:
        inst.region = body.region
    if body.is_active is not None:
        inst.is_active = body.is_active
    if body.metadata_json is not None:
        inst.metadata_json = body.metadata_json

    db.commit()
    db.refresh(inst)
    logger.info("Admin %s updated LMS institution %s", current_user.id, institution_id)
    return inst


@admin_router.delete(
    "/institutions/{institution_id}",
    status_code=204,
    summary="Deactivate institution (admin, soft-delete)",
)
def admin_deactivate_institution(
    institution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> None:
    """Soft-delete: set is_active=False on the institution.  Admin-only."""
    inst = db.query(LMSInstitution).filter(LMSInstitution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found.")
    inst.is_active = False
    db.commit()
    logger.info("Admin %s deactivated LMS institution %s", current_user.id, institution_id)


@admin_router.get(
    "/institutions/{institution_id}/connections",
    response_model=list[AdminConnectionOut],
    summary="List all user connections for an institution (admin)",
)
def admin_list_institution_connections(
    institution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> list[AdminConnectionOut]:
    """Return all LMS connections tied to a specific institution."""
    inst = db.query(LMSInstitution).filter(LMSInstitution.id == institution_id).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found.")
    connections = (
        db.query(LMSConnection)
        .filter(LMSConnection.institution_id == institution_id)
        .order_by(LMSConnection.created_at)
        .all()
    )
    return [_admin_conn_out(c) for c in connections]


# --- Stats ---


@admin_router.get(
    "/stats",
    response_model=LMSStatsOut,
    summary="LMS connection stats by provider + institution (admin)",
)
def admin_lms_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> LMSStatsOut:
    """Return aggregated connection counts by provider and institution."""
    all_connections = db.query(LMSConnection).all()
    total = len(all_connections)

    # Counts by provider → status
    by_provider: dict[str, dict[str, int]] = {}
    for conn in all_connections:
        prov = conn.provider
        status = conn.status
        if prov not in by_provider:
            by_provider[prov] = {}
        by_provider[prov][status] = by_provider[prov].get(status, 0) + 1

    # Active connections per institution
    institutions = db.query(LMSInstitution).all()
    by_institution: list[dict[str, Any]] = []
    for inst in institutions:
        active_count = (
            db.query(func.count(LMSConnection.id))
            .filter(
                LMSConnection.institution_id == inst.id,
                LMSConnection.status == "connected",
            )
            .scalar()
            or 0
        )
        by_institution.append({
            "institution_id": inst.id,
            "name": inst.name,
            "active_connections": active_count,
        })

    # Last-hour sync summary
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    synced_last_hour = sum(
        1
        for c in all_connections
        if c.last_sync_at and c.last_sync_at.replace(tzinfo=timezone.utc) >= one_hour_ago
    )
    errors_last_hour = sum(
        1
        for c in all_connections
        if c.last_sync_at
        and c.last_sync_at.replace(tzinfo=timezone.utc) >= one_hour_ago
        and c.status == "error"
    )

    return LMSStatsOut(
        total_connections=total,
        by_provider=by_provider,
        by_institution=by_institution,
        last_sync_summary={
            "synced_last_hour": synced_last_hour,
            "errors_last_hour": errors_last_hour,
        },
    )


# --- Manual sync trigger ---


@admin_router.post(
    "/sync/trigger",
    response_model=SyncTriggerOut,
    summary="Manually trigger full LMS sync (admin)",
)
async def admin_trigger_full_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> SyncTriggerOut:
    """Immediately run sync_all_connections outside of the scheduler."""
    from app.jobs.lms_sync import sync_all_connections
    result = await sync_all_connections(db)
    logger.info("Admin %s manually triggered full LMS sync: %s", current_user.id, result)
    return SyncTriggerOut(
        synced=result["synced"],
        errors=result["errors"],
        message=f"Sync complete: {result['synced']} synced, {result['errors']} errors.",
    )
