"""MCP (Model Context Protocol) authentication & role-based tool authorization.

CB-CMCP-001 M2-A 2A-1 (#4549) — initial port from ``class-bridge-phase-2``.
CB-CMCP-001 M2-A 2A-3 (#4551) — wire ``BOARD_ADMIN`` / ``CURRICULUM_ADMIN``
into :data:`ROLE_TOOLS` (empty allowlist for now; M3-* / 2B-* stripes
populate per-role tool surface).

MCP clients authenticate by sending a JWT Bearer token in the
``Authorization`` header. The ``fastapi-mcp`` library forwards this header
to each tool invocation, so the same JWT that authenticates REST calls
authenticates MCP tool calls.

This module provides the auth primitives the MCP server will plug into in
later stripes:

1. :func:`verify_mcp_token` — decode-only JWT validation suitable for the
   MCP transport endpoint (no DB hit). Returns an :class:`MCPSession`
   containing the user id, role claim (if any), and raw payload.
2. :func:`authenticate_mcp_request` — FastAPI dependency wrapper around
   :func:`verify_mcp_token` for use as ``AuthConfig.dependencies``.
3. :data:`ROLE_TOOLS` + :func:`get_tools_for_role` — per-role allowlist of
   MCP operation IDs.
4. :func:`assert_role_can_use_tool` — role-assertion helper that raises
   :class:`PermissionError` when a role lacks access to a tool.

This stripe **does not** register MCP routes or instantiate
``FastApiMCP`` — that's 2A-2 territory. As of 2A-3 (#4551), the
``BOARD_ADMIN`` / ``CURRICULUM_ADMIN`` keys exist in :data:`ROLE_TOOLS`
with empty allowlists; their concrete tool surface is filled in by
later M3-E + curriculum-admin stripes.

Per-tool calls in production still go through the existing
``app.api.deps.get_current_user`` dependency, which performs full
validation (user lookup, deletion check, blacklist check). The lightweight
check here is intentionally fast so the MCP transport can reject obviously
invalid tokens without a DB round-trip.

Token-type hardening (PR #4557 review pass-1)
---------------------------------------------
dev-03 mints multiple JWT *types* with the same secret + algorithm
(``access``, ``refresh``, ``email_verify``, ``password_reset``,
``unsubscribe``, ``account_deletion``). Phase-2's port did not gate on
``type``; this implementation rejects everything except ``type=access``
to prevent token-confusion attacks (e.g. a leaked unsubscribe token
authenticating an MCP transport session).

Role-claim caveat (PR #4557 review pass-1)
------------------------------------------
``MCPSession.role`` reflects the JWT ``role`` claim, which dev-03
*does not currently emit* in :func:`app.core.security.create_access_token`.
For production tokens, ``MCPSession.role`` will be ``None``. Callers that
need the authoritative role for tool authorization MUST resolve it from
the ``User`` row (e.g. via :func:`app.api.deps.get_current_user`) and
pass that role string into :func:`assert_role_can_use_tool` rather than
relying on ``MCPSession.role``. Stripe 2A-2 wires this via the per-tool
``get_current_user`` dependency.
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

    .. warning::
       In dev-03, :func:`app.core.security.create_access_token` does not
       emit a ``role`` claim, so ``role`` is typically ``None`` for
       production tokens. Authoritative role-based authorization must
       resolve the role from the ``User`` row (via
       :func:`app.api.deps.get_current_user`) and pass that string into
       :func:`assert_role_can_use_tool`. See module docstring.
    """

    user_id: str
    role: str | None
    payload: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------


_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# JWT ``type`` claim values that dev-03 mints (see ``app/core/security.py``).
# Only ``access`` tokens are valid for MCP transport authentication; any other
# type signed with the same secret (refresh / password_reset / unsubscribe /
# email_verify / account_deletion) MUST be rejected to avoid token confusion.
_ACCESS_TOKEN_TYPE = "access"


def _credentials_exception() -> HTTPException:
    """Build a fresh 401 ``HTTPException`` for each rejected request.

    A new instance per call avoids any risk of cross-request mutation if a
    handler later attaches context to ``.detail`` / ``.headers``. Mirrors
    the pattern used by :func:`app.api.deps.get_current_user`.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_mcp_token(token: str) -> MCPSession:
    """Decode + validate a JWT for the MCP transport.

    Raises :class:`fastapi.HTTPException` with status 401 when the token is
    empty, fails signature verification, has expired, lacks the required
    ``sub`` claim, or carries a non-``access`` ``type`` claim (e.g. a
    refresh / password-reset / unsubscribe / email-verify / account-
    deletion token signed with the same secret).

    The check is decode-only: it does NOT verify the token-blacklist or
    that the user row still exists. Per-tool calls (which are normal
    FastAPI routes guarded by :func:`app.api.deps.get_current_user`) cover
    those cases.
    """
    if not token:
        raise _credentials_exception()

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except JWTError:
        raise _credentials_exception()

    user_id = payload.get("sub")
    if user_id is None:
        raise _credentials_exception()

    # Reject non-access tokens (refresh / email_verify / password_reset /
    # unsubscribe / account_deletion all share the secret + algorithm).
    # ``create_access_token`` (app/core/security.py) always sets
    # ``type=access``; any token without that claim is treated as untrusted.
    if payload.get("type") != _ACCESS_TOKEN_TYPE:
        raise _credentials_exception()

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
# Phase-2 ported the four legacy roles. CB-CMCP-001 M2-A 2A-3 (#4551)
# adds the two new admin roles with empty allowlists so the dispatcher
# recognizes them; concrete tools land in M3-E + later curriculum-admin
# stripes.

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
    # CB-CMCP-001 M2-A 2A-3 (#4551) — populated by future M3-E +
    # curriculum-admin stripes. Empty list intentionally denies all
    # tools today; the explicit key keeps the role visible to the
    # dispatcher (so unknown-role 403 paths don't fire for newly minted
    # users with these roles).
    "BOARD_ADMIN": [],
    "CURRICULUM_ADMIN": [],
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
