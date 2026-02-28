"""
MCP (Model Context Protocol) server integration for ClassBridge.

Exposes safe read-only FastAPI endpoints as MCP tools so that LLM clients
can query courses, assignments, grades, messages, study guides, and
notifications on behalf of authenticated users.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

from app.mcp.auth import create_mcp_auth_config

# ---------------------------------------------------------------------------
# Safe read-only operation IDs exposed via MCP
# ---------------------------------------------------------------------------
# FastAPI auto-generates operationId as "{function_name}_{route_path}_get".
# Only GET endpoints that return data are included — no mutations, no file
# uploads, no auth, no admin actions.
# ---------------------------------------------------------------------------

SAFE_OPERATIONS: list[str] = [
    # Courses
    "list_courses_api_courses__get",
    "get_course_api_courses__course_id__get",
    "list_teaching_courses_api_courses_teaching_get",
    "list_my_created_courses_api_courses_created_me_get",
    "list_my_enrolled_courses_api_courses_enrolled_me_get",
    "get_default_course_api_courses_default_get",
    "list_course_students_api_courses__course_id__students_get",
    # Assignments
    "list_assignments_api_assignments__get",
    "get_assignment_api_assignments__assignment_id__get",
    # Grades
    "get_grade_summary_api_grades_summary_get",
    "get_course_grades_api_grades_course__course_id__get",
    # Messages / Conversations
    "list_conversations_api_messages_conversations_get",
    "get_conversation_api_messages_conversations__conversation_id__get",
    "get_unread_count_api_messages_unread_count_get",
    # Study guides
    "list_study_guides_api_study_guides_get",
    "get_study_guide_api_study_guides__guide_id__get",
    "list_guide_versions_api_study_guides__guide_id__versions_get",
    # Notifications
    "list_notifications_api_notifications__get",
    "get_unread_count_api_notifications_unread_count_get",
    "get_notification_settings_api_notifications_settings_get",
]


def setup_mcp(app: FastAPI) -> FastApiMCP:
    """Create and mount the MCP server on the given FastAPI application.

    The MCP server:
    - Exposes only the safe read-only endpoints listed in ``SAFE_OPERATIONS``.
    - Requires a valid JWT Bearer token (forwarded from the MCP client).
    - Is mounted at ``/mcp`` using the HTTP Streamable transport.
    """
    auth_config = create_mcp_auth_config()

    mcp = FastApiMCP(
        app,
        name="ClassBridge MCP Server",
        description="AI-powered education management platform — read-only data access",
        include_operations=SAFE_OPERATIONS,
        auth_config=auth_config,
    )

    # Use HTTP Streamable transport (recommended over deprecated SSE)
    mcp.mount_http(app, mount_path="/mcp")

    return mcp
