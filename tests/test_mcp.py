"""
Tests for the MCP server foundation (#904) and MCP authentication /
role-based tool authorization (#905).
"""

import secrets

import pytest
from conftest import PASSWORD, _auth, _login

from app.mcp import SAFE_OPERATIONS
from app.mcp.auth import ROLE_TOOLS, get_tools_for_role


# ── Helpers ──────────────────────────────────────────────────────────────

def _register(client, email, role="parent", full_name="MCP Test User"):
    return client.post("/api/auth/register", json={
        "email": email, "password": PASSWORD, "full_name": full_name, "role": role,
    })


def _unique_email(prefix="mcp"):
    return f"{prefix}_{secrets.token_hex(6)}@example.com"


# ── #904: MCP Server Foundation ──────────────────────────────────────────

class TestMCPServerSetup:
    """Verify that the MCP server is mounted and correctly configured."""

    def test_mcp_endpoint_exists(self, client):
        """The /mcp route should exist and respond (even without auth)."""
        # Without auth we should get 401 or 403, not 404
        resp = client.get("/mcp")
        assert resp.status_code != 404, "MCP endpoint should be mounted"

    def test_mcp_config_requires_auth(self, client):
        """GET /api/mcp/config must reject unauthenticated requests."""
        resp = client.get("/api/mcp/config")
        assert resp.status_code == 401

    def test_mcp_config_returns_tools_for_parent(self, client):
        """Authenticated parent should receive MCP config with allowed tools."""
        email = _unique_email("mcp_parent")
        _register(client, email, role="parent")
        headers = _auth(client, email)

        resp = client.get("/api/mcp/config", headers=headers)
        assert resp.status_code == 200
        body = resp.json()

        assert "mcp_url" in body
        assert body["mcp_url"].endswith("/mcp")
        assert body["transport"] == "http"
        assert body["role"] == "PARENT"
        assert isinstance(body["tools"], list)
        assert body["total_tools"] == len(body["tools"])
        assert body["total_tools"] > 0

    def test_mcp_config_returns_tools_for_student(self, client):
        """Authenticated student should receive MCP config with allowed tools."""
        email = _unique_email("mcp_student")
        _register(client, email, role="student")
        headers = _auth(client, email)

        resp = client.get("/api/mcp/config", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "STUDENT"
        assert body["total_tools"] > 0

    def test_mcp_config_returns_tools_for_teacher(self, client):
        """Authenticated teacher should receive MCP config with allowed tools."""
        email = _unique_email("mcp_teacher")
        _register(client, email, role="teacher")
        headers = _auth(client, email)

        resp = client.get("/api/mcp/config", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "TEACHER"
        assert body["total_tools"] > 0


# ── #904: Endpoint Filtering ────────────────────────────────────────────

class TestEndpointFiltering:
    """Verify that only safe read endpoints are exposed via MCP."""

    def test_safe_operations_are_all_get_endpoints(self):
        """Every operation ID in SAFE_OPERATIONS should correspond to a GET."""
        for op_id in SAFE_OPERATIONS:
            assert op_id.endswith("_get"), (
                f"Operation {op_id} does not look like a GET endpoint"
            )

    def test_no_mutation_endpoints_exposed(self):
        """No POST/PUT/PATCH/DELETE operation IDs should be in SAFE_OPERATIONS."""
        mutation_suffixes = ("_post", "_put", "_patch", "_delete")
        for op_id in SAFE_OPERATIONS:
            assert not any(op_id.endswith(s) for s in mutation_suffixes), (
                f"Mutation endpoint {op_id} should not be exposed via MCP"
            )

    def test_no_auth_endpoints_exposed(self):
        """Auth endpoints must never be in the safe operations list."""
        for op_id in SAFE_OPERATIONS:
            assert "auth" not in op_id.lower(), (
                f"Auth endpoint {op_id} should not be exposed via MCP"
            )

    def test_no_admin_endpoints_exposed(self):
        """Admin endpoints must never be in the safe operations list."""
        for op_id in SAFE_OPERATIONS:
            assert "admin" not in op_id.lower(), (
                f"Admin endpoint {op_id} should not be exposed via MCP"
            )

    def test_safe_operations_include_core_read_endpoints(self):
        """Verify the key read endpoints are present."""
        expected_fragments = [
            "list_courses",
            "list_assignments",
            "get_grade_summary",
            "get_course_grades",
            "list_conversations",
            "list_study_guides",
            "list_notifications",
        ]
        for fragment in expected_fragments:
            assert any(fragment in op for op in SAFE_OPERATIONS), (
                f"Expected a safe operation containing '{fragment}'"
            )


# ── #905: Authentication ────────────────────────────────────────────────

class TestMCPAuth:
    """Verify that MCP endpoints require valid JWT authentication."""

    def test_mcp_rejects_no_token(self, client):
        """MCP endpoint should reject requests without a token."""
        resp = client.get("/mcp")
        # Should be 401 or 403, not 200/404
        assert resp.status_code in (401, 403, 405), (
            f"Expected auth rejection, got {resp.status_code}"
        )

    def test_mcp_rejects_invalid_token(self, client):
        """MCP endpoint should reject requests with a bogus token."""
        headers = {"Authorization": "Bearer invalid-token-12345"}
        resp = client.get("/mcp", headers=headers)
        assert resp.status_code in (401, 403, 405), (
            f"Expected auth rejection, got {resp.status_code}"
        )

    def test_mcp_config_rejects_expired_token(self, client, db_session):
        """Expired tokens must be rejected."""
        from datetime import datetime, timedelta, timezone
        from jose import jwt
        from app.core.config import settings

        expired_token = jwt.encode(
            {
                "sub": "99999",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
                "type": "access",
                "jti": "expired-jti",
            },
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        headers = {"Authorization": f"Bearer {expired_token}"}
        resp = client.get("/api/mcp/config", headers=headers)
        assert resp.status_code == 401


# ── #905: Role-Based Tool Authorization ─────────────────────────────────

class TestRoleBasedAuthorization:
    """Verify that tool access is correctly scoped by role."""

    def test_admin_gets_all_tools(self):
        """Admin role should have unrestricted access (None = all)."""
        result = get_tools_for_role("ADMIN")
        assert result is None

    def test_admin_case_insensitive(self):
        """Role lookup should be case-insensitive."""
        assert get_tools_for_role("admin") is None
        assert get_tools_for_role("Admin") is None

    def test_parent_has_limited_tools(self):
        """Parent role should have a specific subset of tools."""
        tools = get_tools_for_role("PARENT")
        assert isinstance(tools, list)
        assert len(tools) > 0
        # Parents should see courses, assignments, grades, messages, notifications
        assert any("courses" in t for t in tools)
        assert any("assignments" in t for t in tools)
        assert any("grades" in t for t in tools)
        assert any("conversations" in t for t in tools)
        assert any("notifications" in t for t in tools)

    def test_student_has_study_guides(self):
        """Student role should include study guide tools."""
        tools = get_tools_for_role("STUDENT")
        assert isinstance(tools, list)
        assert any("study_guides" in t for t in tools)

    def test_parent_no_study_guides(self):
        """Parent role should NOT include study guide tools."""
        tools = get_tools_for_role("PARENT")
        assert isinstance(tools, list)
        assert not any("study_guides" in t for t in tools)

    def test_teacher_has_class_management(self):
        """Teacher role should include teaching-specific tools."""
        tools = get_tools_for_role("TEACHER")
        assert isinstance(tools, list)
        assert any("teaching_courses" in t for t in tools)
        assert any("course_students" in t for t in tools)

    def test_student_no_teaching_tools(self):
        """Student role should NOT include teacher-specific tools."""
        tools = get_tools_for_role("STUDENT")
        assert isinstance(tools, list)
        assert not any("teaching_courses" in t for t in tools)
        assert not any("list_my_created_courses" in t for t in tools)

    def test_unknown_role_gets_empty_list(self):
        """Unknown roles should get an empty tool list (fail-closed)."""
        tools = get_tools_for_role("UNKNOWN_ROLE")
        assert tools == []

    def test_all_role_tools_are_in_safe_operations(self):
        """Every tool listed in ROLE_TOOLS must exist in SAFE_OPERATIONS."""
        for role, tools in ROLE_TOOLS.items():
            if tools is None:
                continue  # Admin — unrestricted
            for tool in tools:
                assert tool in SAFE_OPERATIONS, (
                    f"Tool {tool} for role {role} is not in SAFE_OPERATIONS"
                )

    def test_config_endpoint_reflects_role_tools(self, client):
        """The /api/mcp/config endpoint should return role-appropriate tools."""
        # Register a parent and check their config
        email = _unique_email("mcp_role_check")
        _register(client, email, role="parent")
        headers = _auth(client, email)

        resp = client.get("/api/mcp/config", headers=headers)
        assert resp.status_code == 200
        body = resp.json()

        expected_tools = ROLE_TOOLS["PARENT"]
        assert set(body["tools"]) == set(expected_tools)

    def test_different_roles_get_different_tools(self, client):
        """Parent and student should receive different tool sets."""
        parent_email = _unique_email("mcp_parent_diff")
        student_email = _unique_email("mcp_student_diff")
        _register(client, parent_email, role="parent")
        _register(client, student_email, role="student")

        parent_resp = client.get("/api/mcp/config", headers=_auth(client, parent_email))
        student_resp = client.get("/api/mcp/config", headers=_auth(client, student_email))

        parent_tools = set(parent_resp.json()["tools"])
        student_tools = set(student_resp.json()["tools"])

        # They should overlap on some tools but not be identical
        assert parent_tools != student_tools
        # Both should have course listing
        assert any("list_courses" in t for t in parent_tools)
        assert any("list_courses" in t for t in student_tools)
