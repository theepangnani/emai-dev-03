"""
MCP (Model Context Protocol) server integration for ClassBridge.

Exposes safe read-only FastAPI endpoints as MCP tools so that LLM clients
can query courses, assignments, grades, messages, study guides, and
notifications on behalf of authenticated users.

Also mounts the active MCP tool routers:
- /api/mcp/tools/study  — study material generation tools (#908)
- /api/mcp/tools/tutor  — AI tutor agent tools (#909)
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

from app.mcp.auth import create_mcp_auth_config
from app.mcp.tools.study import router as study_tools_router
from app.mcp.tools.tutor import router as tutor_tools_router

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
    # Student Academic Context Resources (#906)
    "get_student_profile_api_mcp_resources_student__student_id__profile_get",
    "get_student_assignments_api_mcp_resources_student__student_id__assignments_get",
    "get_student_study_history_api_mcp_resources_student__student_id__study_history_get",
    "get_student_weak_areas_api_mcp_resources_student__student_id__weak_areas_get",
    "get_student_summary_api_mcp_tools_student__student_id__summary_get",
    "identify_knowledge_gaps_api_mcp_tools_student__student_id__knowledge_gaps_get",
    # Google Classroom Tools (#907)
    "list_classroom_courses_api_mcp_tools_classroom_courses_get",
    "list_classroom_assignments_api_mcp_tools_classroom_courses__course_id__assignments_get",
    "get_classroom_materials_api_mcp_tools_classroom_courses__course_id__materials_get",
    "get_classroom_grades_api_mcp_tools_classroom_courses__course_id__grades_get",
    "get_sync_status_api_mcp_tools_classroom_sync_status_get",
    # MCP Study Material Generation Tools (#908)
    "mcp_list_study_materials",
    "mcp_get_study_material",
    "mcp_search_study_materials",
    "mcp_generate_study_guide",
    "mcp_generate_quiz",
    "mcp_generate_flashcards",
    "mcp_convert_study_material",
    # MCP AI Tutor Agent (#909)
    "mcp_create_study_plan",
    "mcp_get_study_recommendations",
    "mcp_analyze_study_effectiveness",
]


def setup_mcp(app: FastAPI) -> FastApiMCP:
    """Create and mount the MCP server on the given FastAPI application.

    The MCP server:
    - Registers MCP resource and tool routers (student context, Google Classroom).
    - Exposes only the safe read-only endpoints listed in ``SAFE_OPERATIONS``.
    - Requires a valid JWT Bearer token (forwarded from the MCP client).
    - Is mounted at ``/mcp`` using the HTTP Streamable transport.

    Additionally registers the active MCP tool routers so that the tool
    endpoints (study material generation, AI tutor agent) are reachable at
    /api/mcp/tools/... before the MCP server is set up (so FastApiMCP can
    discover them and include them in the tool manifest).
    """
    # Register MCP-specific API routes BEFORE creating the FastApiMCP instance
    # so that fastapi-mcp can discover them.
    from app.mcp.routes import register_mcp_routes

    register_mcp_routes(app)

    # Register MCP tool routers on the FastAPI app so that:
    # 1. They are accessible as normal REST endpoints at /api/mcp/tools/...
    # 2. FastApiMCP discovers them and exposes them as MCP tools.
    app.include_router(study_tools_router)
    app.include_router(tutor_tools_router)

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
