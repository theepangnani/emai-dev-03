"""
MCP route registration.

Aggregates all MCP resource and tool routers so that main.py only needs
a single import and include_router call (or the setup_mcp function wires
them in via this module).
"""

from __future__ import annotations

from fastapi import FastAPI

from app.mcp.resources.student import router as student_resources_router
from app.mcp.resources.student import tools_router as student_tools_router
from app.mcp.tools.google_classroom import router as classroom_router
from app.mcp.tools.google_classroom import sync_router as classroom_sync_router


def register_mcp_routes(app: FastAPI) -> None:
    """Mount all MCP resource + tool routers under /api."""
    app.include_router(student_resources_router, prefix="/api")
    app.include_router(student_tools_router, prefix="/api")
    app.include_router(classroom_router, prefix="/api")
    app.include_router(classroom_sync_router, prefix="/api")
