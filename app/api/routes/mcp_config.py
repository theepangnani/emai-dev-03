"""
MCP configuration endpoint.

Allows authenticated clients to discover the MCP server URL and the tools
available for their role.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_current_user, require_feature
from app.mcp import SAFE_OPERATIONS
from app.mcp.auth import get_tools_for_role
from app.models.user import User

router = APIRouter(prefix="/mcp", tags=["mcp"])


@router.get("/config")
def get_mcp_config(
    request: Request,
    _flag=Depends(require_feature("mcp_tools")),
    current_user: User = Depends(get_current_user),
):
    """Return MCP server URL and available tools for the authenticated user.

    This endpoint is intended for MCP client bootstrapping — it tells the
    client where the MCP server lives and which tools the current user's
    role is allowed to invoke.
    """
    # Determine the role (prefer the legacy single-role field for simplicity)
    role = (current_user.role or "").upper()
    if not role and current_user.roles:
        # Multi-role: pick the highest-privilege role
        roles_str = current_user.roles or ""
        role_list = [r.strip().upper() for r in roles_str.split(",") if r.strip()]
        # Priority: ADMIN > TEACHER > PARENT > STUDENT
        priority = ["ADMIN", "TEACHER", "PARENT", "STUDENT"]
        for p in priority:
            if p in role_list:
                role = p
                break
        if not role and role_list:
            role = role_list[0]

    # Compute allowed tools for this role
    allowed = get_tools_for_role(role)
    if allowed is None:
        # Admin — all safe operations are available
        tools = SAFE_OPERATIONS
    else:
        tools = allowed

    # Build the MCP server URL relative to the current request
    base_url = str(request.base_url).rstrip("/")
    mcp_url = f"{base_url}/mcp"

    return {
        "mcp_url": mcp_url,
        "transport": "http",
        "role": role,
        "tools": tools,
        "total_tools": len(tools),
    }
