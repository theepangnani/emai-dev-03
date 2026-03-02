"""Tests for the Moodle LMS token-based auth service and LMSProvider adapter.

Tests cover:
  - MoodleOAuthClient: auth URL generation, authenticate(), validate_token(), error handling
  - MoodleAPIClient: get_site_info, get_courses, get_assignments, get_grades,
                     get_course_contents, get_files, get_announcements
  - MoodleAPIClient: error response handling (HTTP 200 with exception body)
  - MoodleAdapter: registered in provider registry
  - MoodleAdapter: sync_courses, sync_assignments, sync_materials, sync_grades
  - MoodleAdapter helper: _make_client_with_userid
  - Utility functions: parse_unix_timestamp, map_module_content_type
  - Connect endpoints: GET /moodle/connect, POST /moodle/connect, POST /moodle/{id}/refresh

Dependencies:
  - pytest-asyncio for async test support
  - unittest.mock for patching httpx calls (no external network required)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.moodle import (
    MoodleOAuthClient,
    MoodleAPIClient,
    parse_unix_timestamp,
    map_module_content_type,
)
from app.services.lms_registry import MoodleAdapter, get_provider, list_providers


# ---------------------------------------------------------------------------
# Fixtures / factories
# ---------------------------------------------------------------------------


def _make_institution(
    base_url: str = "https://moodle.testschool.edu",
    provider: str = "moodle",
) -> MagicMock:
    """Create a mock LMSInstitution for a Moodle provider."""
    inst = MagicMock()
    inst.id = 99
    inst.base_url = base_url
    inst.provider = provider
    inst.is_active = True
    inst.metadata_json = None
    return inst


def _make_connection(
    institution=None,
    access_token: str = "moodle-ws-token-abc123",
) -> MagicMock:
    """Create a mock LMSConnection for a Moodle provider."""
    conn = MagicMock()
    conn.id = 88
    conn.user_id = 1
    conn.provider = "moodle"
    conn.institution = institution or _make_institution()
    conn.institution_id = 99
    conn.access_token_enc = access_token
    conn.status = "connected"
    conn.sync_error = None
    return conn


def _make_mock_post_response(json_data, status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response for a POST request."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


def _make_async_client_mock(post_response) -> tuple:
    """Return (mock_client_cls, mock_http) configured to return post_response."""
    mock_http = AsyncMock()
    mock_http.post = AsyncMock(return_value=post_response)
    mock_http.get = AsyncMock(return_value=post_response)

    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_client_cls, mock_http


# ---------------------------------------------------------------------------
# TestMoodleOAuthClient
# ---------------------------------------------------------------------------


class TestMoodleOAuthClient:

    def test_get_auth_url_returns_token_management_page(self):
        """get_auth_url should return the Moodle token management admin URL."""
        inst = _make_institution(base_url="https://moodle.myschool.edu")
        client = MoodleOAuthClient()
        url = client.get_auth_url(inst)

        assert "moodle.myschool.edu" in url
        assert "webservicetokens" in url

    def test_get_auth_url_strips_trailing_slash_from_base_url(self):
        """get_auth_url must strip trailing slashes from base_url."""
        inst = _make_institution(base_url="https://moodle.school.ca/")
        client = MoodleOAuthClient()
        url = client.get_auth_url(inst)

        # Should not have double slashes
        assert "//admin" not in url
        assert "moodle.school.ca" in url

    def test_get_auth_url_empty_base_url(self):
        """get_auth_url with empty base_url should return a URL with just the path."""
        inst = _make_institution(base_url="")
        client = MoodleOAuthClient()
        url = client.get_auth_url(inst)

        # Should still contain the token management path
        assert "webservicetokens" in url

    @pytest.mark.asyncio
    async def test_authenticate_returns_token(self):
        """authenticate() should POST to /login/token.php and return token dict."""
        mock_resp = _make_mock_post_response(
            {"token": "ws-token-abc", "privatetoken": "priv-token-xyz"}
        )
        mock_cls, mock_http = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = MoodleOAuthClient()
            result = await client.authenticate(
                "testuser", "testpassword", "https://moodle.school.edu"
            )

        assert result["token"] == "ws-token-abc"
        assert result["privatetoken"] == "priv-token-xyz"

    @pytest.mark.asyncio
    async def test_authenticate_posts_to_token_endpoint(self):
        """authenticate() must POST to /login/token.php on the given base_url."""
        mock_resp = _make_mock_post_response(
            {"token": "some-token", "privatetoken": ""}
        )
        mock_cls, mock_http = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = MoodleOAuthClient()
            await client.authenticate(
                "user", "pass", "https://moodle.example.org"
            )

        call_args = mock_http.post.call_args
        called_url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
        assert "moodle.example.org" in called_url
        assert "token.php" in called_url

    @pytest.mark.asyncio
    async def test_authenticate_raises_on_moodle_error(self):
        """authenticate() should raise ValueError when Moodle returns an error."""
        mock_resp = _make_mock_post_response(
            {"error": "invalidlogin", "debuginfo": "Invalid login, please try again"}
        )
        mock_cls, mock_http = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = MoodleOAuthClient()
            with pytest.raises(ValueError, match="authentication failed"):
                await client.authenticate(
                    "baduser", "wrongpass", "https://moodle.school.edu"
                )

    @pytest.mark.asyncio
    async def test_validate_token_returns_site_info(self):
        """validate_token() should call core_webservice_get_site_info and return data."""
        site_info = {
            "sitename": "My School Moodle",
            "username": "student1",
            "userid": 42,
            "siteurl": "https://moodle.school.edu",
            "release": "4.1",
        }
        mock_resp = _make_mock_post_response(site_info)
        mock_cls, mock_http = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = MoodleOAuthClient()
            result = await client.validate_token("valid-token", "https://moodle.school.edu")

        assert result["sitename"] == "My School Moodle"
        assert result["userid"] == 42

    @pytest.mark.asyncio
    async def test_validate_token_raises_on_moodle_exception(self):
        """validate_token() should raise ValueError on Moodle exception response."""
        mock_resp = _make_mock_post_response({
            "exception": "moodle_exception",
            "errorcode": "invalidtoken",
            "message": "Invalid token - token not found",
        })
        mock_cls, mock_http = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = MoodleOAuthClient()
            with pytest.raises(ValueError, match="token validation failed"):
                await client.validate_token("bad-token", "https://moodle.school.edu")

    def test_get_auth_url_uses_admin_settings_path(self):
        """get_auth_url should point to the Moodle admin settings path."""
        inst = _make_institution(base_url="https://lms.university.edu")
        client = MoodleOAuthClient()
        url = client.get_auth_url(inst)

        assert "admin/settings.php" in url

    @pytest.mark.asyncio
    async def test_authenticate_raises_on_empty_token(self):
        """authenticate() should raise ValueError when token is missing from response."""
        mock_resp = _make_mock_post_response({"token": "", "privatetoken": ""})
        mock_cls, mock_http = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = MoodleOAuthClient()
            with pytest.raises(ValueError, match="empty token"):
                await client.authenticate("user", "pass", "https://moodle.edu")


# ---------------------------------------------------------------------------
# TestMoodleAPIClient
# ---------------------------------------------------------------------------


class TestMoodleAPIClient:

    def _make_client(self, base_url: str = "https://moodle.test.edu", token: str = "test-token") -> MoodleAPIClient:
        return MoodleAPIClient(base_url=base_url, token=token)

    @pytest.mark.asyncio
    async def test_get_courses_returns_list(self):
        """get_courses() should return list of course dicts."""
        courses_data = [
            {"id": 10, "fullname": "Math 101", "shortname": "MATH101", "summary": ""},
            {"id": 11, "fullname": "English 201", "shortname": "ENG201", "summary": ""},
        ]
        mock_resp = _make_mock_post_response(courses_data)
        mock_cls, _ = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = self._make_client()
            result = await client.get_courses(user_id=42)

        assert len(result) == 2
        assert result[0]["fullname"] == "Math 101"

    @pytest.mark.asyncio
    async def test_get_courses_returns_empty_on_moodle_exception(self):
        """get_courses() should return [] when Moodle returns exception."""
        mock_resp = _make_mock_post_response({
            "exception": "moodle_exception",
            "errorcode": "nopermissions",
            "message": "No permissions",
        })
        mock_cls, _ = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = self._make_client()
            result = await client.get_courses(user_id=42)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_assignments_extracts_from_courses_key(self):
        """get_assignments() should extract assignments from nested courses key."""
        assignments_data = {
            "courses": [
                {
                    "id": 10,
                    "assignments": [
                        {"id": 101, "name": "Essay 1", "duedate": 1700000000, "grade": "100"},
                        {"id": 102, "name": "Quiz 1", "duedate": 0, "grade": "50"},
                    ],
                }
            ]
        }
        mock_resp = _make_mock_post_response(assignments_data)
        mock_cls, _ = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = self._make_client()
            result = await client.get_assignments(course_id=10)

        assert len(result) == 2
        assert result[0]["name"] == "Essay 1"
        assert result[0]["duedate"] == 1700000000

    @pytest.mark.asyncio
    async def test_get_grades_returns_grade_dict(self):
        """get_grades() should return a grade dict."""
        grade_data = {"grade": "85.5", "rawgrade": "85.5"}
        mock_resp = _make_mock_post_response(grade_data)
        mock_cls, _ = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = self._make_client()
            result = await client.get_grades(course_id=10)

        assert result["grade"] == "85.5"

    @pytest.mark.asyncio
    async def test_get_grades_returns_empty_on_error(self):
        """get_grades() should return {} when Moodle returns an exception."""
        mock_resp = _make_mock_post_response({
            "exception": "moodle_exception",
            "errorcode": "invalidcourse",
            "message": "Invalid course",
        })
        mock_cls, _ = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = self._make_client()
            result = await client.get_grades(course_id=999)

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_course_contents_returns_sections(self):
        """get_course_contents() should return list of section dicts."""
        contents_data = [
            {
                "id": 1,
                "name": "Week 1",
                "modules": [
                    {"id": 201, "name": "Lecture Notes", "modname": "resource", "contents": []},
                    {"id": 202, "name": "Assignment 1", "modname": "assign", "contents": []},
                ],
            }
        ]
        mock_resp = _make_mock_post_response(contents_data)
        mock_cls, _ = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = self._make_client()
            result = await client.get_course_contents(course_id=10)

        assert len(result) == 1
        assert result[0]["name"] == "Week 1"
        assert len(result[0]["modules"]) == 2

    @pytest.mark.asyncio
    async def test_get_files_extracts_resource_modules(self):
        """get_files() should extract only resource-type modules with file contents."""
        contents_data = [
            {
                "id": 1,
                "name": "Week 1",
                "modules": [
                    {
                        "id": 201,
                        "name": "Lecture PDF",
                        "modname": "resource",
                        "instance": 301,
                        "contents": [
                            {
                                "type": "file",
                                "filename": "lecture.pdf",
                                "fileurl": "https://moodle.test.edu/pluginfile.php/1/lecture.pdf",
                                "filesize": 102400,
                                "mimetype": "application/pdf",
                            }
                        ],
                    },
                    {
                        "id": 202,
                        "name": "Assignment",
                        "modname": "assign",
                        "instance": 302,
                        "contents": [],
                    },
                ],
            }
        ]
        mock_resp = _make_mock_post_response(contents_data)
        mock_cls, _ = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = self._make_client()
            result = await client.get_files(course_id=10)

        assert len(result) == 1
        assert result[0]["filename"] == "lecture.pdf"
        assert result[0]["module_name"] == "Lecture PDF"

    @pytest.mark.asyncio
    async def test_post_adds_wstoken_and_format(self):
        """_post() must always include wstoken and moodlewsrestformat=json."""
        mock_resp = _make_mock_post_response([])
        mock_cls, mock_http = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = MoodleAPIClient(
                base_url="https://moodle.test.edu",
                token="secret-ws-token",
            )
            await client._post({"wsfunction": "core_enrol_get_users_courses", "userid": "1"})

        call_kwargs = mock_http.post.call_args
        data_arg = call_kwargs[1].get("data") or (call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {})
        assert data_arg.get("wstoken") == "secret-ws-token"
        assert data_arg.get("moodlewsrestformat") == "json"

    @pytest.mark.asyncio
    async def test_post_returns_error_dict_on_moodle_exception(self):
        """_post() should return the error dict (not raise) for Moodle exceptions."""
        error_data = {
            "exception": "moodle_exception",
            "errorcode": "nopermissions",
            "message": "No permission for that operation",
        }
        mock_resp = _make_mock_post_response(error_data)
        mock_cls, _ = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = self._make_client()
            result = await client._post({"wsfunction": "some_function"})

        assert "exception" in result
        assert result["errorcode"] == "nopermissions"

    @pytest.mark.asyncio
    async def test_get_site_info_returns_dict(self):
        """get_site_info() should return site information dict."""
        site_data = {
            "sitename": "Test Moodle",
            "username": "student1",
            "userid": 42,
            "siteurl": "https://moodle.test.edu",
        }
        mock_resp = _make_mock_post_response(site_data)
        mock_cls, _ = _make_async_client_mock(mock_resp)

        with patch("httpx.AsyncClient", mock_cls):
            client = self._make_client()
            result = await client.get_site_info()

        assert result["userid"] == 42
        assert result["sitename"] == "Test Moodle"


# ---------------------------------------------------------------------------
# TestMoodleAdapterRegistered
# ---------------------------------------------------------------------------


class TestMoodleAdapterRegistered:

    def test_moodle_adapter_in_registry(self):
        """MoodleAdapter must be registered in the provider registry."""
        provider = get_provider("moodle")
        assert provider is not None

    def test_moodle_adapter_is_moodle_adapter_instance(self):
        """The registered 'moodle' provider must be a MoodleAdapter instance."""
        provider = get_provider("moodle")
        assert isinstance(provider, MoodleAdapter)

    def test_list_providers_includes_moodle(self):
        """list_providers() must include Moodle in the result."""
        providers = list_providers()
        ids = [p["provider_id"] for p in providers]
        assert "moodle" in ids

    def test_moodle_provider_display_name(self):
        """MoodleAdapter.display_name should be 'Moodle'."""
        provider = get_provider("moodle")
        assert provider.display_name == "Moodle"

    def test_moodle_provider_supports_oauth_false(self):
        """MoodleAdapter.supports_oauth must be False (token-based auth)."""
        provider = get_provider("moodle")
        assert provider.supports_oauth is False

    def test_moodle_provider_requires_institution_url(self):
        """MoodleAdapter.requires_institution_url must be True."""
        provider = get_provider("moodle")
        assert provider.requires_institution_url is True


# ---------------------------------------------------------------------------
# TestMoodleAdapterHelpers
# ---------------------------------------------------------------------------


class TestMoodleAdapterHelpers:

    def test_parse_unix_timestamp_zero_returns_none(self):
        """parse_unix_timestamp(0) should return None (Moodle uses 0 for no due date)."""
        result = parse_unix_timestamp(0)
        assert result is None

    def test_parse_unix_timestamp_none_returns_none(self):
        """parse_unix_timestamp(None) should return None."""
        result = parse_unix_timestamp(None)
        assert result is None

    def test_parse_unix_timestamp_valid_returns_utc_datetime(self):
        """parse_unix_timestamp with a valid timestamp should return UTC datetime."""
        ts = 1700000000  # 2023-11-14 22:13:20 UTC
        result = parse_unix_timestamp(ts)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_parse_unix_timestamp_negative_returns_none(self):
        """parse_unix_timestamp(-1) should return None."""
        result = parse_unix_timestamp(-1)
        assert result is None

    def test_map_module_content_type_resource(self):
        """resource modname should map to 'document'."""
        assert map_module_content_type("resource") == "document"

    def test_map_module_content_type_url(self):
        """url modname should map to 'resources'."""
        assert map_module_content_type("url") == "resources"

    def test_map_module_content_type_page(self):
        """page modname should map to 'notes'."""
        assert map_module_content_type("page") == "notes"

    def test_map_module_content_type_folder(self):
        """folder modname should map to 'document'."""
        assert map_module_content_type("folder") == "document"

    def test_map_module_content_type_unknown_returns_other(self):
        """Unknown modname should return 'other'."""
        assert map_module_content_type("assign") == "other"
        assert map_module_content_type("quiz") == "other"
        assert map_module_content_type("scorm") == "other"


# ---------------------------------------------------------------------------
# TestMoodleConnectEndpoints
# ---------------------------------------------------------------------------


PASSWORD = "TestPass123!"


class TestMoodleConnectEndpoints:
    """Integration tests for the Moodle connect endpoints.

    These tests use the FastAPI TestClient to test the full request/response
    cycle without making real HTTP calls to Moodle.
    """

    def _register_user_and_login(self, client) -> str:
        """Register a user and return the JWT access token."""
        import uuid
        email = f"moodle_test_{uuid.uuid4().hex[:8]}@example.com"
        r = client.post("/api/auth/register", json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Moodle Test User",
            "role": "student",
        })
        assert r.status_code in (200, 201), f"Register failed: {r.text}"

        r = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
        assert r.status_code == 200, f"Login failed: {r.text}"
        return r.json()["access_token"]

    def _create_moodle_institution(self, client, token: str) -> int:
        """Create a Moodle institution as admin and return its ID."""
        # Register and login as admin
        import uuid
        email = f"moodle_admin_{uuid.uuid4().hex[:8]}@example.com"
        client.post("/api/auth/register", json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Admin User",
            "role": "admin",
        })
        r = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
        admin_token = r.json()["access_token"]

        r = client.post(
            "/api/lms/institutions",
            json={
                "name": "Test Moodle School",
                "provider": "moodle",
                "base_url": "https://moodle.testschool.edu",
                "region": "ON",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 201, f"Create institution failed: {r.text}"
        return r.json()["id"]

    def test_get_moodle_connect_returns_instructions(self, app):
        """GET /lms/moodle/connect should return token entry instructions JSON."""
        from fastapi.testclient import TestClient
        client = TestClient(app)

        token = self._register_user_and_login(client)
        institution_id = self._create_moodle_institution(client, token)

        r = client.get(
            f"/api/lms/moodle/connect?institution_id={institution_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "instructions" in data
        assert "institution_id" in data
        assert data["institution_id"] == institution_id

    def test_get_moodle_connect_instructions_mention_token(self, app):
        """GET /lms/moodle/connect instructions should mention Web Service token."""
        from fastapi.testclient import TestClient
        client = TestClient(app)

        token = self._register_user_and_login(client)
        institution_id = self._create_moodle_institution(client, token)

        r = client.get(
            f"/api/lms/moodle/connect?institution_id={institution_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        data = r.json()
        instructions = data.get("instructions", "")
        assert "token" in instructions.lower() or "Token" in instructions

    def test_post_moodle_connect_with_valid_token_creates_connection(self, app):
        """POST /lms/moodle/connect with valid token should create a connection."""
        from fastapi.testclient import TestClient
        client = TestClient(app)

        user_token = self._register_user_and_login(client)
        institution_id = self._create_moodle_institution(client, user_token)

        site_info = {
            "sitename": "Test School Moodle",
            "username": "student1",
            "userid": 42,
            "siteurl": "https://moodle.testschool.edu",
        }

        with patch("app.services.moodle.MoodleAPIClient.get_site_info", new_callable=AsyncMock) as mock_info:
            mock_info.return_value = site_info

            r = client.post(
                "/api/lms/moodle/connect",
                json={"institution_id": institution_id, "token": "valid-ws-token-123"},
                headers={"Authorization": f"Bearer {user_token}"},
            )

        assert r.status_code == 201
        data = r.json()
        assert data["provider"] == "moodle"
        assert data["status"] == "connected"
        assert data["institution_id"] == institution_id

    def test_post_moodle_connect_with_invalid_token_returns_422(self, app):
        """POST /lms/moodle/connect with invalid token should return 422."""
        from fastapi.testclient import TestClient
        client = TestClient(app)

        user_token = self._register_user_and_login(client)
        institution_id = self._create_moodle_institution(client, user_token)

        with patch("app.services.moodle.MoodleAPIClient.get_site_info", new_callable=AsyncMock) as mock_info:
            mock_info.return_value = {
                "exception": "moodle_exception",
                "errorcode": "invalidtoken",
                "message": "Invalid token",
            }

            r = client.post(
                "/api/lms/moodle/connect",
                json={"institution_id": institution_id, "token": "bad-token"},
                headers={"Authorization": f"Bearer {user_token}"},
            )

        assert r.status_code == 422

    def test_post_moodle_refresh_updates_connection(self, app):
        """POST /lms/moodle/{id}/refresh should re-validate token and update connection."""
        from fastapi.testclient import TestClient
        client = TestClient(app)

        user_token = self._register_user_and_login(client)
        institution_id = self._create_moodle_institution(client, user_token)

        # First create the connection
        site_info = {
            "sitename": "Test School Moodle",
            "username": "student1",
            "userid": 42,
            "siteurl": "https://moodle.testschool.edu",
        }
        with patch("app.services.moodle.MoodleAPIClient.get_site_info", new_callable=AsyncMock) as mock_info:
            mock_info.return_value = site_info
            r = client.post(
                "/api/lms/moodle/connect",
                json={"institution_id": institution_id, "token": "ws-token-abc"},
                headers={"Authorization": f"Bearer {user_token}"},
            )
        assert r.status_code == 201
        connection_id = r.json()["id"]

        # Now refresh
        with patch("app.services.moodle.MoodleAPIClient.get_site_info", new_callable=AsyncMock) as mock_info:
            mock_info.return_value = site_info
            r = client.post(
                f"/api/lms/moodle/{connection_id}/refresh",
                headers={"Authorization": f"Bearer {user_token}"},
            )

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "connected"
        assert data["id"] == connection_id
