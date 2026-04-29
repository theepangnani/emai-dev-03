"""MCP (Model Context Protocol) authentication & role-based tool authorization.

CB-CMCP-001 M2-A 2A-1 (#4549) — initial port from ``class-bridge-phase-2``.

MCP clients authenticate by sending a JWT Bearer token in the
``Authorization`` header. The ``fastapi-mcp`` library forwards this header
to each tool invocation, so the same JWT that authenticates REST calls
authenticates MCP tool calls.

This module provides the auth primitives the MCP server will plug into in
later stripes:

1. :func:`verify_mcp_token` — decode-only JWT validation suitable for the
   MCP transport endpoint (no DB hit). Returns an :class:`MCPSession`
   containing the user id, role, and raw payload.
2. :func:`authenticate_mcp_request` — FastAPI dependency wrapper around
   :func:`verify_mcp_token` for use as ``AuthConfig.dependencies``.
3. :data:`ROLE_TOOLS` + :func:`get_tools_for_role` — per-role allowlist of
   MCP operation IDs.
4. :func:`assert_role_can_use_tool` — role-assertion helper that raises
   :class:`PermissionError` when a role lacks access to a tool.

This stripe **does not** register MCP routes or instantiate
``FastApiMCP`` — that's 2A-2 territory. It also does **not** wire role
entries for ``BOARD_ADMIN`` / ``CURRICULUM_ADMIN`` — that's 2A-3.

Per-tool calls in production still go through the existing
``app.api.deps.get_current_user`` dependency, which performs full
validation (user lookup, deletion check, blacklist check). The lightweight
check here is intentionally fast so the MCP transport can reject obviously
invalid tokens without a DB round-trip.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import settings

# ---------------------------------------------------------------------------
# Session container
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MCPSession:
    """Lightweight session view for an authenticated MCP request.

    Carries the JWT subject (user id, as a string per OAuth2 convention),
    the optional role claim, and the raw decoded payload. Frozen so
    consumers can rely on identity over the request lifetime.

    The role field is intentionally a plain string (not :class:`UserRole`)
    so that rolling out new role values (e.g. ``BOARD_ADMIN``,
    ``CURRICULUM_ADMIN`` in 2A-3) does not require a code change to the
    decode path — :func:`get_tools_for_role` is the single point of
    role-vs-tools validation.
    """

    user_id: str
    role: str | None
    payload: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------


_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing authentication token",
    headers={"WWW-Authenticate": "Bearer"},
)


def verify_mcp_token(token: str) -> MCPSession:
    """Decode + validate a JWT for the MCP transport.

    Raises :class:`fastapi.HTTPException` with status 401 when the token is
    missing the required ``sub`` claim, fails signature verification, or
    has expired.

    The check is decode-only: it does NOT verify the token-blacklist or
    that the user row still exists. Per-tool calls (which are normal
    FastAPI routes guarded by :func:`app.api.deps.get_current_user`) cover
    those cases.
    """
    if not token:
        raise _CREDENTIALS_EXCEPTION

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    user_id = payload.get("sub")
    if user_id is None:
        raise _CREDENTIALS_EXCEPTION

    return MCPSession(
        user_id=str(user_id),
        role=payload.get("role"),
        payload=payload,
    )


async def authenticate_mcp_request(
    token: str = Depends(_oauth2_scheme),
) -> MCPSession:
    """FastAPI dependency that authenticates an MCP transport request.

    Designed to be plugged into ``fastapi_mcp.AuthConfig.dependencies`` in
    stripe 2A-2. Returns the resolved :class:`MCPSession` so downstream
    dependencies can read ``user_id`` / ``role`` without re-decoding.
    """
    return verify_mcp_token(token)


# ---------------------------------------------------------------------------
# Role-based tool authorization
# ---------------------------------------------------------------------------

# Maps each role to the subset of MCP operation IDs it may invoke.
# ``None`` means *all* tools (admin).
#
# This is the ported phase-2 mapping. ``BOARD_ADMIN`` / ``CURRICULUM_ADMIN``
# entries land in 2A-3 (CB-CMCP-001 M2-A) when their tool surface is
# defined; do not extend this dict here.

ROLE_TOOLS: dict[str, list[str] | None] = {
    "PARENT": [
        # Courses
        "list_courses_api_courses__get",
        "get_course_api_courses__course_id__get",
        "get_default_course_api_courses_default_get",
        "list_course_students_api_courses__course_id__students_get",
        # Assignments
        "list_assignments_api_assignments__get",
        "get_assignment_api_assignments__assignment_id__get",
        # Grades
        "get_grade_summary_api_grades_summary_get",
        "get_course_grades_api_grades_course__course_id__get",
        # Messages
        "list_conversations_api_messages_conversations_get",
        "get_conversation_api_messages_conversations__conversation_id__get",
        "get_unread_count_api_messages_unread_count_get",
        # Notifications
        "list_notifications_api_notifications__get",
        "get_unread_count_api_notifications_unread_count_get",
        "get_notification_settings_api_notifications_settings_get",
    ],
    "STUDENT": [
        # Courses
        "list_courses_api_courses__get",
        "get_course_api_courses__course_id__get",
        "list_my_enrolled_courses_api_courses_enrolled_me_get",
        "get_default_course_api_courses_default_get",
        # Assignments
        "list_assignments_api_assignments__get",
        "get_assignment_api_assignments__assignment_id__get",
        # Grades
        "get_grade_summary_api_grades_summary_get",
        "get_course_grades_api_grades_course__course_id__get",
        # Study guides
        "list_study_guides_api_study_guides_get",
        "get_study_guide_api_study_guides__guide_id__get",
        "list_guide_versions_api_study_guides__guide_id__versions_get",
        # Notifications
        "list_notifications_api_notifications__get",
        "get_unread_count_api_notifications_unread_count_get",
        "get_notification_settings_api_notifications_settings_get",
    ],
    "TEACHER": [
        # Courses
        "list_courses_api_courses__get",
        "get_course_api_courses__course_id__get",
        "list_teaching_courses_api_courses_teaching_get",
        "list_my_created_courses_api_courses_created_me_get",
        "get_default_course_api_courses_default_get",
        "list_course_students_api_courses__course_id__students_get",
        # Assignments
        "list_assignments_api_assignments__get",
        "get_assignment_api_assignments__assignment_id__get",
        # Grades
        "get_grade_summary_api_grades_summary_get",
        "get_course_grades_api_grades_course__course_id__get",
        # Messages
        "list_conversations_api_messages_conversations_get",
        "get_conversation_api_messages_conversations__conversation_id__get",
        "get_unread_count_api_messages_unread_count_get",
        # Notifications
        "list_notifications_api_notifications__get",
        "get_unread_count_api_notifications_unread_count_get",
        "get_notification_settings_api_notifications_settings_get",
    ],
    "ADMIN": None,  # Full access to all MCP tools
}


def _normalize_role(role: str | None) -> str:
    """Return the canonical (uppercase) form of a role label.

    Accepts both the SQL-stored values (``"parent"``, ``"BOARD_ADMIN"``)
    and the enum names (``"PARENT"``). Empty / ``None`` becomes the empty
    string so unknown lookups return ``[]``.
    """
    return (role or "").strip().upper()


def get_tools_for_role(role: str | None) -> list[str] | None:
    """Return the list of allowed MCP operation IDs for *role*.

    Returns ``None`` when the role has unrestricted access (admin). Falls
    back to an empty list for unknown / missing roles. Lookup is
    case-insensitive against :data:`ROLE_TOOLS` keys.
    """
    key = _normalize_role(role)
    if not key:
        return []
    return ROLE_TOOLS.get(key, [])


def assert_role_can_use_tool(role: str | None, tool_id: str) -> None:
    """Raise :class:`PermissionError` when *role* cannot invoke *tool_id*.

    Returns ``None`` on success. ``ADMIN`` (and any other role mapped to
    ``None`` in :data:`ROLE_TOOLS`) is treated as having unrestricted
    access. Unknown roles always fail.
    """
    allowed = get_tools_for_role(role)
    if allowed is None:
        # ``None`` sentinel == unrestricted access.
        return
    if tool_id not in allowed:
        raise PermissionError(
            f"Role {_normalize_role(role) or '<none>'!r} is not permitted "
            f"to invoke MCP tool {tool_id!r}"
        )


__all__ = [
    "MCPSession",
    "ROLE_TOOLS",
    "assert_role_can_use_tool",
    "authenticate_mcp_request",
    "get_tools_for_role",
    "verify_mcp_token",
]
