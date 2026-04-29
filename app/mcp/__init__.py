"""MCP (Model Context Protocol) server integration for ClassBridge.

CB-CMCP-001 M2 (#4549, #4550) — initial port from ``class-bridge-phase-2``.

Exposes safe read-only FastAPI endpoints as MCP tools so that LLM clients
(e.g. Claude Desktop) can query courses, assignments, grades, messages,
study guides, and notifications on behalf of authenticated users.

Stripe progression
------------------
- 2A-1 (#4549) — auth scaffolding (this module's ``auth`` import).
- 2A-2 (#4550) — native MCP transport router + tool registry (this
  module's ``routes`` + ``tools`` re-exports).
- 2A-3 — wire ``BOARD_ADMIN`` / ``CURRICULUM_ADMIN`` role entries into
  :data:`app.mcp.auth.ROLE_TOOLS` and per-tool ``roles`` allowlists.
- 2B-* — concrete MCP tool implementations (replace the stub handlers
  in :data:`app.mcp.tools.TOOLS`).
"""
from __future__ import annotations

from app.mcp.auth import (
    MCPSession,
    ROLE_TOOLS,
    assert_role_can_use_tool,
    authenticate_mcp_request,
    get_tools_for_role,
    verify_mcp_token,
)
from app.mcp.routes import (
    MCP_FEATURE_FLAG_KEY,
    require_mcp_enabled,
    router as mcp_router,
)
from app.mcp.tools import (
    MCPNotImplementedError,
    TOOLS,
    ToolDescriptor,
    get_tool,
    list_tools_for_role,
)

__all__ = [
    "MCPSession",
    "MCPNotImplementedError",
    "MCP_FEATURE_FLAG_KEY",
    "ROLE_TOOLS",
    "TOOLS",
    "ToolDescriptor",
    "assert_role_can_use_tool",
    "authenticate_mcp_request",
    "get_tool",
    "get_tools_for_role",
    "list_tools_for_role",
    "mcp_router",
    "require_mcp_enabled",
    "verify_mcp_token",
]
