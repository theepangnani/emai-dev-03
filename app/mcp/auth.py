"""
MCP authentication and role-based tool authorization.

MCP clients authenticate by sending a JWT Bearer token in the Authorization
header.  The ``fastapi-mcp`` library forwards this header to each tool
invocation (it includes ``'authorization'`` in its forwarded headers by
default), so the existing ``get_current_user`` dependency validates the token
exactly as it does for normal REST calls.

This module provides:

1. **Auth dependency** — used by ``AuthConfig.dependencies`` so that the MCP
   transport endpoints themselves require a valid JWT.
2. **Role-based tool mapping** — defines which MCP tools each role is allowed
   to invoke.  The ``/api/mcp/config`` endpoint uses this to tell clients
   which tools are available for the authenticated user.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import settings
from fastapi_mcp import AuthConfig

# ---------------------------------------------------------------------------
# MCP auth dependency
# ---------------------------------------------------------------------------

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def authenticate_mcp_request(
    request: Request,
    token: str = Depends(_oauth2_scheme),
) -> dict:
    """Validate the Bearer token on MCP transport requests.

    This is intentionally a lightweight check (decode-only, no DB hit) so
    that the MCP endpoint itself can reject clearly invalid tokens quickly.
    The per-tool call still goes through ``get_current_user`` which performs
    full validation including token-blacklist checking.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    return payload


def create_mcp_auth_config() -> AuthConfig:
    """Build an ``AuthConfig`` that protects MCP endpoints with JWT auth."""
    return AuthConfig(
        dependencies=[Depends(authenticate_mcp_request)],
    )


# ---------------------------------------------------------------------------
# Role-based tool authorization
# ---------------------------------------------------------------------------

# Maps each role to the subset of MCP operation IDs it may invoke.
# ``None`` means *all* tools (admin).

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


def get_tools_for_role(role: str) -> list[str] | None:
    """Return the list of allowed MCP operation IDs for *role*.

    Returns ``None`` when the role has unrestricted access (admin).
    Falls back to an empty list for unknown roles.
    """
    return ROLE_TOOLS.get(role.upper(), [])
