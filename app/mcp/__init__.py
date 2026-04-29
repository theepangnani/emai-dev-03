"""MCP (Model Context Protocol) server integration for ClassBridge.

CB-CMCP-001 M2 (#4549) — initial port from ``class-bridge-phase-2``.

Exposes safe read-only FastAPI endpoints as MCP tools so that LLM clients
(e.g. Claude Desktop) can query courses, assignments, grades, messages,
study guides, and notifications on behalf of authenticated users.

This stripe (2A-1) ships only the auth scaffolding so that subsequent
stripes can plug it into ``fastapi_mcp.AuthConfig.dependencies`` and the
per-tool authorization layer:

- 2A-2 — register MCP routes + mount the ``FastApiMCP`` server
- 2A-3 — wire ``BOARD_ADMIN`` / ``CURRICULUM_ADMIN`` role entries into
  :data:`app.mcp.auth.ROLE_TOOLS`
- 2B-* — concrete MCP tool implementations
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

__all__ = [
    "MCPSession",
    "ROLE_TOOLS",
    "assert_role_can_use_tool",
    "authenticate_mcp_request",
    "get_tools_for_role",
    "verify_mcp_token",
]
