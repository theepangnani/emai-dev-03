"""MCP transport routes.

CB-CMCP-001 M2-A 2A-2 (#4550) — port + adapt phase-2's MCP entry-point
into a native FastAPI router (no ``fastapi_mcp`` dependency).

Endpoints
---------
- ``POST /mcp/initialize``  — handshake; returns server identity + tool
  count for the caller's role. Used by MCP clients to verify the
  transport is reachable + authorized before issuing tool calls.
- ``GET /mcp/list_tools``    — return the tool catalog filtered by the
  caller's authoritative role (resolved from the ``User`` row, NOT the
  JWT claim — see 2A-1 module docstring).
- ``POST /mcp/call_tool``   — dispatch a tool by name with a JSON
  ``arguments`` body. Returns the tool's result, or 501 if the tool is
  a stub (2B-* not yet implemented), 404 if unknown, 403 if the
  caller's role lacks access.

Auth + flag gating
------------------
All three routes go through :func:`require_mcp_enabled`, which:

1. Resolves the caller via :func:`app.api.deps.get_current_user`. This
   inherits the existing dev-03 JWT validation surface (signature, exp,
   blacklist, deletion check) and — critically — performs a DB lookup
   so the caller's role is *authoritative* (not the JWT ``role`` claim,
   which 2A-1 documented is ``None`` in production).
2. Verifies the access token is ``type=access`` via 2A-1's
   :func:`app.mcp.auth.verify_mcp_token`. ``get_current_user`` does
   NOT enforce ``type``, so a leaked refresh / unsubscribe / password-
   reset token would otherwise authenticate the MCP transport.
3. Checks the ``mcp.enabled`` feature flag and returns ``403`` when
   it's OFF. Auth resolution happens *first* so unauth callers always
   see ``401`` regardless of flag state — flag-state probing without a
   valid token is not possible.

Why a separate flag from ``cmcp.enabled``
-----------------------------------------
CB-CMCP-001 reuses ``cmcp.enabled`` for the curriculum + content-
generation REST surface. The MCP transport is a separate trust boundary
(LLM clients can authenticate as any user, whereas the REST surface is
human-driven), so we gate it under its own ``mcp.enabled`` key. This
lets ops keep the REST features on while keeping the MCP transport off
during initial rollout, and vice-versa.

Out of scope (deferred to later stripes)
----------------------------------------
- Streaming / SSE transport (the phase-2 ``mcp.mount_http`` plumbing);
  this stripe ships only the polling-style JSON endpoints.
- Concrete 2B-* tool implementations (``get_expectations``,
  ``get_artifact``, ``list_catalog``, ``generate_content``) — they
  return 501 here.
- BOARD_ADMIN / CURRICULUM_ADMIN role wiring — that's 2A-3.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.mcp.auth import verify_mcp_token
from app.mcp.tools import (
    MCPNotImplementedError,
    get_tool,
    list_tools_for_role,
)
from app.models.user import User
from app.services.feature_flag_service import is_feature_enabled

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

MCP_FEATURE_FLAG_KEY = "mcp.enabled"

# Reuses the OAuth2 token URL from the rest of the app so the OpenAPI
# auth dialog points at the same login route. ``auto_error=True`` here so
# missing-bearer requests get a 401 from the dependency chain itself
# (matches ``app.api.deps.oauth2_scheme``).
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def require_mcp_enabled(
    token: str = Depends(_oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: 401 if unauthed / wrong token type, 403 if flag OFF.

    Order of checks matters:

    1. ``OAuth2PasswordBearer`` short-circuits with 401 when no token is
       presented. This is enforced by FastAPI before this function runs.
    2. ``get_current_user`` validates the JWT signature + exp + blacklist
       + user-row existence + deletion status. Failures raise 401.
    3. :func:`verify_mcp_token` adds the strict ``type=access`` check
       that ``get_current_user`` doesn't enforce — so a refresh /
       unsubscribe / password-reset token signed with the same secret
       can't authenticate an MCP transport session (#4557 hardening).
    4. The flag check is last so unauth requests always see 401, never
       a 403 that would leak flag state to anonymous probers.
    """
    # Re-validate token type. ``get_current_user`` already decoded the
    # JWT for its own checks, but it doesn't gate on ``type``; running
    # ``verify_mcp_token`` here adds the access-token-type assertion
    # without coupling this module to ``get_current_user``'s internals.
    verify_mcp_token(token)

    if not is_feature_enabled(MCP_FEATURE_FLAG_KEY, db=db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="MCP transport is not enabled",
        )
    return current_user


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class InitializeResponse(BaseModel):
    """Response body for ``POST /mcp/initialize``.

    Carries the server identity (so MCP clients can pin compatible
    revisions) and the count of tools the caller may invoke (so a client
    can early-exit if the user has zero tools available — e.g. a pure
    BOARD_ADMIN today).
    """

    name: str = "ClassBridge MCP Server"
    description: str = (
        "AI-powered education management platform — read-only data + "
        "curriculum-aligned content generation."
    )
    protocol_version: str = "2024-11-05"
    available_tools: int


class ToolEntry(BaseModel):
    """One row in the ``GET /mcp/list_tools`` response."""

    name: str
    description: str
    input_schema: dict[str, Any]


class ListToolsResponse(BaseModel):
    """Catalog response for ``GET /mcp/list_tools``."""

    tools: list[ToolEntry]


class CallToolRequest(BaseModel):
    """Request body for ``POST /mcp/call_tool``.

    *arguments* is a free-form JSON object that the dispatcher forwards
    to the tool handler. Per-tool validation lives in the handler (which
    can use the tool's ``input_schema`` for stricter checks) — keeping
    it loose here means we don't duplicate Pydantic models for every
    tool surface.
    """

    name: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class CallToolResponse(BaseModel):
    """Successful tool invocation result.

    The shape mirrors the MCP spec's ``CallToolResult`` loosely — we
    return ``content`` as a JSON-serializable dict rather than the spec's
    multi-part content array, since all current 2B-* tools return JSON.
    Future stripes can add a ``content_type`` discriminator if a tool
    needs to return text/markdown/blob.
    """

    name: str
    content: Any


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


router = APIRouter(prefix="/mcp", tags=["MCP"])


@router.post("/initialize", response_model=InitializeResponse)
def initialize(
    current_user: User = Depends(require_mcp_enabled),
) -> InitializeResponse:
    """Handshake endpoint — confirms transport is reachable + authorized.

    Returns the server identity and the count of tools the caller may
    invoke (computed from their authoritative role on the ``User``
    row — see module docstring).
    """
    role = current_user.role.value if current_user.role is not None else None
    available = list_tools_for_role(role)
    return InitializeResponse(available_tools=len(available))


@router.get("/list_tools", response_model=ListToolsResponse)
def list_tools(
    current_user: User = Depends(require_mcp_enabled),
) -> ListToolsResponse:
    """Return the tool catalog filtered by the caller's role.

    Tool entries omit server-side concerns (handler reference, role
    allowlist) — the public schema is exactly what an MCP client needs
    to render a "what can I ask for" surface.
    """
    role = current_user.role.value if current_user.role is not None else None
    tools = list_tools_for_role(role)
    return ListToolsResponse(
        tools=[ToolEntry(**t.to_public_dict()) for t in tools]
    )


@router.post("/call_tool", response_model=CallToolResponse)
def call_tool(
    payload: CallToolRequest,
    current_user: User = Depends(require_mcp_enabled),
    db: Session = Depends(get_db),
) -> CallToolResponse:
    """Dispatch a tool by name with the supplied arguments.

    Failure modes (in order):

    - Unknown tool name → ``404 Not Found``. We do not differentiate
      "doesn't exist" vs "exists but you can't see it" because the
      registry is small and stable; leaking the existence of a tool the
      caller's role can't see has no security cost.
    - Caller's role lacks access → ``403 Forbidden``. Re-checked here
      defensively even though ``list_tools`` already filters by role —
      a client could call ``call_tool`` directly without consulting the
      catalog, and the registry is the single source of truth.
    - Stub tool (2B-* not yet implemented) → ``501 Not Implemented``
      with the tool name in the detail.
    - Any other handler exception bubbles up. Concrete 2B-* handlers
      should raise ``HTTPException`` directly for known failures.
    """
    descriptor = get_tool(payload.name)
    if descriptor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown MCP tool: {payload.name!r}",
        )

    role = current_user.role.value if current_user.role is not None else None
    if not descriptor.is_role_allowed(role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role {(role or '<none>')!r} is not permitted to invoke MCP "
                f"tool {payload.name!r}"
            ),
        )

    try:
        result = descriptor.handler(payload.arguments, current_user, db)
    except MCPNotImplementedError as exc:
        # Stub tool path. We log at INFO so ops can spot rollout-blocked
        # invocations without polluting WARN/ERROR.
        logger.info(
            "mcp.call_tool.stub name=%s user_id=%s",
            payload.name,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        ) from exc

    return CallToolResponse(name=payload.name, content=result)


__all__ = [
    "MCP_FEATURE_FLAG_KEY",
    "router",
    "require_mcp_enabled",
]
