"""LMS Connections API routes — Multi-LMS Provider Framework (#22, #23).

Routes:
  GET    /api/lms/providers                  — list available providers
  GET    /api/lms/institutions               — list institutions (filterable by provider)
  POST   /api/lms/institutions               — create institution (admin only)
  GET    /api/lms/connections                — list user's connections
  POST   /api/lms/connections                — create/register a connection
  PATCH  /api/lms/connections/{id}           — update label or status
  DELETE /api/lms/connections/{id}           — remove connection
  GET    /api/lms/connections/{id}/status    — sync status for a connection
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.api.deps import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.lms_institution import LMSInstitution
from app.models.lms_connection import LMSConnection
from app.services.lms_registry import list_providers, get_provider

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


VALID_STATUSES = {"connected", "expired", "error", "disconnected"}
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
