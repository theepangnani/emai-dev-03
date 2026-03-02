"""Tests for the Canvas LMS OAuth2 service and LMSProvider adapter.

Tests cover:
  - CanvasOAuthClient: auth URL generation, code exchange, token refresh
  - CanvasAPIClient: courses, modules, assignments, grades, announcements, files
  - CanvasAPIClient: Link-header pagination, retry on 429 rate limit
  - CanvasAdapter: sync_courses, sync_assignments, sync_materials, sync_grades
  - CanvasAdapter: registered in provider registry
  - OAuth2 flow endpoints: /api/lms/canvas/connect, /callback, /refresh

Dependencies:
  - pytest-asyncio for async test support
  - unittest.mock for patching httpx calls (no external network required)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from conftest import PASSWORD
from app.services.canvas import CanvasOAuthClient, CanvasAPIClient
from app.services.lms_registry import CanvasAdapter, get_provider, list_providers


# ---------------------------------------------------------------------------
# Fixtures / factories
# ---------------------------------------------------------------------------


def _make_institution(
    base_url: str = "https://testschool.instructure.com",
    client_id: str = "canvas-client-id",
    client_secret: str = "canvas-client-secret",
) -> MagicMock:
    """Create a mock LMSInstitution with Canvas metadata_json OAuth credentials."""
    inst = MagicMock()
    inst.id = 77
    inst.base_url = base_url
    inst.provider = "canvas"
    inst.is_active = True
    inst.metadata_json = json.dumps(
        {"client_id": client_id, "client_secret": client_secret}
    )
    return inst


def _make_connection(
    institution=None,
    access_token: str = "canvas-access-token",
    refresh_token: str = "canvas-refresh-token",
) -> MagicMock:
    """Create a mock LMSConnection for a Canvas provider."""
    conn = MagicMock()
    conn.id = 55
    conn.user_id = 1
    conn.provider = "canvas"
    conn.institution = institution or _make_institution()
    conn.institution_id = 77
    conn.access_token_enc = access_token
    conn.refresh_token_enc = refresh_token
    conn.status = "connected"
    conn.sync_error = None
    return conn


def _make_mock_response(
    json_data,
    status_code: int = 200,
    headers: dict | None = None,
) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    resp.headers = headers or {}
    return resp


# ---------------------------------------------------------------------------
# CanvasOAuthClient tests
# ---------------------------------------------------------------------------


class TestCanvasOAuthClient:

    def test_generate_auth_url_uses_canvas_format(self):
        """Auth URL must use Canvas /login/oauth2/auth path."""
        inst = _make_institution(base_url="https://myschool.instructure.com")
        oauth = CanvasOAuthClient()
        url = oauth.generate_auth_url(inst, "https://app.example.com/callback", "test-state")

        assert "myschool.instructure.com" in url
        assert "/login/oauth2/auth" in url

    def test_generate_auth_url_includes_client_id(self):
        """Auth URL must include client_id from institution metadata."""
        inst = _make_institution(client_id="unique-canvas-client-id")
        oauth = CanvasOAuthClient()
        url = oauth.generate_auth_url(inst, "https://app.example.com/callback", "state")

        assert "unique-canvas-client-id" in url

    def test_generate_auth_url_includes_state(self):
        """Auth URL must include the CSRF state parameter."""
        inst = _make_institution()
        oauth = CanvasOAuthClient()
        url = oauth.generate_auth_url(inst, "https://example.com/cb", "csrf-state-xyz")

        assert "csrf-state-xyz" in url

    def test_generate_auth_url_includes_redirect_uri(self):
        """Auth URL must include redirect_uri parameter."""
        inst = _make_institution()
        oauth = CanvasOAuthClient()
        url = oauth.generate_auth_url(inst, "https://app.example.com/callback", "state")

        assert "redirect_uri" in url

    def test_generate_auth_url_response_type_code(self):
        """Auth URL must request response_type=code for Authorization Code flow."""
        inst = _make_institution()
        oauth = CanvasOAuthClient()
        url = oauth.generate_auth_url(inst, "https://example.com/cb", "state")

        assert "response_type=code" in url

    def test_generate_auth_url_includes_scopes(self):
        """Auth URL must include the scope parameter for Canvas API access."""
        inst = _make_institution()
        oauth = CanvasOAuthClient()
        url = oauth.generate_auth_url(inst, "https://example.com/cb", "state")

        assert "scope=" in url

    @pytest.mark.asyncio
    async def test_exchange_code_returns_tokens(self):
        """exchange_code must POST to /login/oauth2/token and return token dict."""
        inst = _make_institution()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-canvas-access-token",
            "refresh_token": "new-canvas-refresh-token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            oauth = CanvasOAuthClient()
            result = await oauth.exchange_code(inst, "auth-code-abc", "https://example.com/cb")

        assert result["access_token"] == "new-canvas-access-token"
        assert result["refresh_token"] == "new-canvas-refresh-token"
        assert result["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_exchange_code_posts_to_token_endpoint(self):
        """exchange_code must POST to the Canvas token endpoint URL."""
        inst = _make_institution(base_url="https://myschool.instructure.com")
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "token",
            "refresh_token": "refresh",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            oauth = CanvasOAuthClient()
            await oauth.exchange_code(inst, "code", "https://example.com/cb")

        # Verify the POST was called with the Canvas token URL
        call_args = mock_http.post.call_args
        token_url = call_args[0][0]
        assert "myschool.instructure.com" in token_url
        assert "/login/oauth2/token" in token_url

    @pytest.mark.asyncio
    async def test_refresh_access_token_returns_new_tokens(self):
        """refresh_access_token must return a new access token."""
        inst = _make_institution()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "refreshed-canvas-token",
            "refresh_token": "refreshed-canvas-refresh",
            "expires_in": 7200,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            oauth = CanvasOAuthClient()
            result = await oauth.refresh_access_token(inst, "old-refresh-token")

        assert result["access_token"] == "refreshed-canvas-token"
        assert result["expires_in"] == 7200

    def test_get_client_id_from_metadata_json(self):
        """_get_client_id must extract client_id from institution metadata_json."""
        inst = _make_institution(client_id="extracted-canvas-id")
        result = CanvasOAuthClient._get_client_id(inst)
        assert result == "extracted-canvas-id"

    def test_get_client_secret_from_metadata_json(self):
        """_get_client_secret must extract client_secret from institution metadata_json."""
        inst = _make_institution(client_secret="extracted-canvas-secret")
        result = CanvasOAuthClient._get_client_secret(inst)
        assert result == "extracted-canvas-secret"

    def test_get_client_id_returns_empty_when_no_metadata(self):
        """_get_client_id returns empty string when metadata_json is None."""
        inst = MagicMock()
        inst.metadata_json = None
        result = CanvasOAuthClient._get_client_id(inst)
        assert result == ""


# ---------------------------------------------------------------------------
# CanvasAPIClient tests
# ---------------------------------------------------------------------------


class TestCanvasAPIClient:

    @pytest.mark.asyncio
    async def test_get_courses_returns_list(self):
        """get_courses must return a list of Canvas course dicts."""
        courses = [
            {"id": 101, "name": "Calculus I", "course_code": "MATH101"},
            {"id": 102, "name": "Physics II", "course_code": "PHYS201"},
        ]
        mock_resp = _make_mock_response(courses, headers={"Link": ""})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            api = CanvasAPIClient("https://myschool.instructure.com", "token")
            result = await api.get_courses()

        assert len(result) == 2
        assert result[0]["name"] == "Calculus I"

    @pytest.mark.asyncio
    async def test_sync_courses_maps_canvas_course(self):
        """sync_courses in CanvasAdapter must map Canvas course fields to Course model."""
        canvas_courses = [
            {
                "id": 201,
                "name": "Biology 101",
                "course_code": "BIO101",
                "sis_course_id": "sis-bio-101",
            }
        ]

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        added: list = []

        def fake_add(obj):
            obj.id = len(added) + 1
            added.append(obj)

        db.add = fake_add
        db.commit = MagicMock()
        db.refresh = MagicMock()

        connection = _make_connection()

        with patch(
            "app.services.canvas.CanvasAPIClient.get_courses",
            new_callable=AsyncMock,
            return_value=canvas_courses,
        ):
            adapter = CanvasAdapter()
            result = await adapter.sync_courses(connection, db)

        assert len(result) == 1
        assert result[0].name == "Biology 101"
        assert result[0].lms_provider == "canvas"
        assert result[0].lms_external_id == "201"
        assert result[0].subject_code == "BIO101"

    @pytest.mark.asyncio
    async def test_sync_assignments_maps_due_date(self):
        """sync_assignments must parse due_at ISO 8601 string into due_date."""
        canvas_assignments = [
            {
                "id": 301,
                "name": "Homework 1",
                "due_at": "2026-05-15T23:59:00Z",
                "points_possible": 100.0,
            }
        ]

        mock_course = MagicMock()
        mock_course.id = 10
        mock_course.lms_external_id = "201"

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [mock_course]
        db.query.return_value.filter.return_value.first.return_value = None

        added: list = []

        def fake_add(obj):
            obj.id = len(added) + 1
            added.append(obj)

        db.add = fake_add
        db.commit = MagicMock()
        db.refresh = MagicMock()

        connection = _make_connection()

        with patch(
            "app.services.canvas.CanvasAPIClient.get_assignments",
            new_callable=AsyncMock,
            return_value=canvas_assignments,
        ):
            adapter = CanvasAdapter()
            result = await adapter.sync_assignments(connection, db)

        assert len(result) == 1
        assert result[0].title == "Homework 1"
        assert result[0].due_date is not None
        assert result[0].due_date.year == 2026
        assert result[0].due_date.month == 5
        assert result[0].max_points == 100.0

    @pytest.mark.asyncio
    async def test_sync_materials_maps_module_items(self):
        """sync_materials must create CourseContent from Canvas module items."""
        modules = [
            {
                "id": 401,
                "name": "Week 1",
                "items": [
                    {"id": 501, "title": "Lecture Notes", "type": "File", "url": "https://example.com/file"},
                    {"id": 502, "title": "Khan Academy", "type": "ExternalUrl", "external_url": "https://khanacademy.org"},
                    {"id": 503, "title": "Intro Page", "type": "Page", "url": "/pages/intro"},
                ],
            }
        ]

        mock_course = MagicMock()
        mock_course.id = 10
        mock_course.lms_external_id = "201"

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [mock_course]
        db.query.return_value.filter.return_value.first.return_value = None

        added: list = []

        def fake_add(obj):
            obj.id = len(added) + 1
            added.append(obj)

        db.add = fake_add
        db.commit = MagicMock()
        db.refresh = MagicMock()

        connection = _make_connection()

        with patch(
            "app.services.canvas.CanvasAPIClient.get_course_modules",
            new_callable=AsyncMock,
            return_value=modules,
        ):
            adapter = CanvasAdapter()
            result = await adapter.sync_materials(connection, db)

        assert len(result) == 3
        types = {m.content_type for m in result}
        assert "document" in types      # File
        assert "resources" in types     # ExternalUrl
        assert "notes" in types         # Page

    @pytest.mark.asyncio
    async def test_link_pagination_followed(self):
        """_get_all_pages must follow rel="next" Link headers until exhausted."""
        page1_resp = _make_mock_response(
            [{"id": 1, "name": "Course A"}],
            headers={
                "Link": '<https://school.instructure.com/api/v1/courses?page=2>; rel="next", '
                        '<https://school.instructure.com/api/v1/courses?page=1>; rel="first"'
            },
        )
        page2_resp = _make_mock_response(
            [{"id": 2, "name": "Course B"}],
            headers={"Link": '<https://school.instructure.com/api/v1/courses?page=1>; rel="first"'},
        )

        responses = [page1_resp, page2_resp]
        call_count = 0

        async def fake_get(*args, **kwargs):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = fake_get
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            api = CanvasAPIClient("https://school.instructure.com", "token")
            result = await api._get_all_pages(
                "https://school.instructure.com/api/v1/courses",
                {"Authorization": "Bearer token", "Accept": "application/json"},
                {"per_page": 50},
            )

        assert len(result) == 2
        names = {item["name"] for item in result}
        assert "Course A" in names
        assert "Course B" in names

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self):
        """_fetch_with_retry must retry on HTTP 429 and eventually succeed."""
        rate_limit_resp = _make_mock_response([], status_code=429, headers={"Retry-After": "0"})
        rate_limit_resp.raise_for_status = MagicMock(side_effect=None)

        success_resp = _make_mock_response(
            [{"id": 1, "name": "Course X"}],
            headers={"Link": ""},
        )

        call_count = 0

        async def fake_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return rate_limit_resp
            return success_resp

        with patch("httpx.AsyncClient") as mock_cls:
            with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                mock_http = AsyncMock()
                mock_http.get = fake_get
                mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
                mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

                api = CanvasAPIClient("https://school.instructure.com", "token")
                headers = {"Authorization": "Bearer token", "Accept": "application/json"}
                response = await api._fetch_with_retry(mock_http, "https://school.instructure.com/api/v1/courses", headers, None)

        assert response is success_resp
        assert call_count == 2
        # asyncio.sleep was called once (on the 429)
        mock_sleep.assert_called_once()

    def test_parse_link_next_extracts_url(self):
        """_parse_link_next must extract the rel="next" URL from a Link header."""
        link_header = (
            '<https://school.instructure.com/api/v1/courses?page=3>; rel="next", '
            '<https://school.instructure.com/api/v1/courses?page=1>; rel="first", '
            '<https://school.instructure.com/api/v1/courses?page=5>; rel="last"'
        )
        result = CanvasAPIClient._parse_link_next(link_header)
        assert result == "https://school.instructure.com/api/v1/courses?page=3"

    def test_parse_link_next_returns_none_when_no_next(self):
        """_parse_link_next must return None when there is no rel="next" link."""
        link_header = (
            '<https://school.instructure.com/api/v1/courses?page=1>; rel="first", '
            '<https://school.instructure.com/api/v1/courses?page=5>; rel="last"'
        )
        result = CanvasAPIClient._parse_link_next(link_header)
        assert result is None

    def test_parse_link_next_returns_none_for_empty_header(self):
        """_parse_link_next must return None for an empty Link header."""
        result = CanvasAPIClient._parse_link_next("")
        assert result is None


# ---------------------------------------------------------------------------
# CanvasAdapter registry tests
# ---------------------------------------------------------------------------


class TestCanvasAdapterRegistered:

    def test_canvas_adapter_registered_in_registry(self):
        """CanvasAdapter must appear in the global provider registry."""
        from app.services.lms_registry import _REGISTRY
        assert "canvas" in _REGISTRY

    def test_canvas_in_list_providers(self):
        """list_providers() must include canvas."""
        providers = list_providers()
        provider_ids = [p["provider_id"] for p in providers]
        assert "canvas" in provider_ids

    def test_canvas_adapter_is_correct_type(self):
        """The registered adapter must be a CanvasAdapter instance."""
        from app.services.lms_registry import _REGISTRY
        assert isinstance(_REGISTRY["canvas"], CanvasAdapter)

    def test_canvas_adapter_metadata(self):
        """CanvasAdapter must report correct provider metadata."""
        adapter = CanvasAdapter()
        assert adapter.provider_id == "canvas"
        assert adapter.display_name == "Canvas LMS"
        assert adapter.supports_oauth is True
        assert adapter.requires_institution_url is True

    def test_canvas_adapter_get_auth_url(self):
        """CanvasAdapter.get_auth_url must return a URL pointing to canvas connect."""
        adapter = CanvasAdapter()
        url = adapter.get_auth_url(user_id=1, redirect_uri="https://example.com/cb")
        assert "/canvas/connect" in url


# ---------------------------------------------------------------------------
# CanvasAdapter helper tests
# ---------------------------------------------------------------------------


class TestCanvasAdapterHelpers:

    def test_parse_iso_date_valid(self):
        """_parse_iso_date must parse a valid ISO 8601 date string."""
        adapter = CanvasAdapter()
        result = adapter._parse_iso_date("2026-06-20T23:59:00Z")
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 6
        assert result.day == 20

    def test_parse_iso_date_none_returns_none(self):
        """_parse_iso_date must return None for None input."""
        adapter = CanvasAdapter()
        assert adapter._parse_iso_date(None) is None

    def test_parse_iso_date_empty_returns_none(self):
        """_parse_iso_date must return None for empty string input."""
        adapter = CanvasAdapter()
        assert adapter._parse_iso_date("") is None

    def test_map_item_type_file(self):
        """_map_item_type must map 'File' to 'document'."""
        assert CanvasAdapter._map_item_type("File") == "document"

    def test_map_item_type_external_url(self):
        """_map_item_type must map 'ExternalUrl' to 'resources'."""
        assert CanvasAdapter._map_item_type("ExternalUrl") == "resources"

    def test_map_item_type_page(self):
        """_map_item_type must map 'Page' to 'notes'."""
        assert CanvasAdapter._map_item_type("Page") == "notes"

    def test_map_item_type_other(self):
        """_map_item_type must map unknown types to 'other'."""
        assert CanvasAdapter._map_item_type("Discussion") == "other"
        assert CanvasAdapter._map_item_type("") == "other"
        assert CanvasAdapter._map_item_type("Assignment") == "other"


# ---------------------------------------------------------------------------
# Canvas OAuth2 endpoint tests (integration — uses TestClient)
# ---------------------------------------------------------------------------


class TestCanvasOAuthEndpoints:

    def test_connect_endpoint_redirects_to_canvas(self, client, db_session):
        """GET /api/lms/canvas/connect must redirect to Canvas OAuth URL."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.models.lms_institution import LMSInstitution

        email = "canvas_connect_test@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                full_name="Canvas Connect Test",
                role=UserRole.STUDENT,
                hashed_password=get_password_hash(PASSWORD),
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        inst = LMSInstitution(
            name="Test Canvas School",
            provider="canvas",
            base_url="https://testcanvas.instructure.com",
            is_active=True,
            metadata_json=json.dumps({"client_id": "cid", "client_secret": "csec"}),
        )
        db_session.add(inst)
        db_session.commit()
        db_session.refresh(inst)

        token_resp = client.post(
            "/api/auth/login",
            data={"username": email, "password": PASSWORD},
        )
        token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get(
            f"/api/lms/canvas/connect?institution_id={inst.id}",
            headers=headers,
            follow_redirects=False,
        )

        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "testcanvas.instructure.com" in location
        assert "/login/oauth2/auth" in location

    def test_connect_endpoint_invalid_institution_returns_404(self, client, db_session):
        """GET /api/lms/canvas/connect with unknown institution_id must return 404."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        email = "canvas_404_test@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                full_name="Canvas 404",
                role=UserRole.STUDENT,
                hashed_password=get_password_hash(PASSWORD),
            )
            db_session.add(user)
            db_session.commit()

        token_resp = client.post(
            "/api/auth/login",
            data={"username": email, "password": PASSWORD},
        )
        token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get(
            "/api/lms/canvas/connect?institution_id=999999",
            headers=headers,
            follow_redirects=False,
        )
        assert resp.status_code == 404

    def test_connect_endpoint_wrong_provider_returns_422(self, client, db_session):
        """GET /api/lms/canvas/connect with a Brightspace institution must return 422."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.models.lms_institution import LMSInstitution

        email = "canvas_422_test@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                full_name="Canvas 422",
                role=UserRole.STUDENT,
                hashed_password=get_password_hash(PASSWORD),
            )
            db_session.add(user)
            db_session.commit()

        # Create a Brightspace institution (not canvas)
        inst = LMSInstitution(
            name="Wrong Provider",
            provider="brightspace",
            base_url="https://wrong.brightspace.com",
            is_active=True,
        )
        db_session.add(inst)
        db_session.commit()
        db_session.refresh(inst)

        token_resp = client.post(
            "/api/auth/login",
            data={"username": email, "password": PASSWORD},
        )
        token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get(
            f"/api/lms/canvas/connect?institution_id={inst.id}",
            headers=headers,
            follow_redirects=False,
        )
        assert resp.status_code == 422

    def test_callback_creates_lms_connection(self, client, db_session):
        """GET /api/lms/canvas/callback must create an LMSConnection on success."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.models.lms_institution import LMSInstitution
        from app.api.routes.lms_connections import _canvas_oauth_state

        email = "canvas_callback@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                full_name="Canvas Callback",
                role=UserRole.STUDENT,
                hashed_password=get_password_hash(PASSWORD),
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        inst = LMSInstitution(
            name="Canvas Callback School",
            provider="canvas",
            base_url="https://callback.instructure.com",
            is_active=True,
            metadata_json=json.dumps({"client_id": "ci3", "client_secret": "cs3"}),
        )
        db_session.add(inst)
        db_session.commit()
        db_session.refresh(inst)

        # Seed state as if /connect was called
        state_token = "canvas-state-token-callback-test"
        _canvas_oauth_state[state_token] = {
            "user_id": user.id,
            "institution_id": inst.id,
        }

        with patch(
            "app.api.routes.lms_connections.CanvasOAuthClient"
        ) as MockCanvasOAuth:
            mock_instance = AsyncMock()
            mock_instance.exchange_code = AsyncMock(
                return_value={
                    "access_token": "canvas-at-from-callback",
                    "refresh_token": "canvas-rt-from-callback",
                    "expires_in": 3600,
                }
            )
            MockCanvasOAuth.return_value = mock_instance

            resp = client.get(
                f"/api/lms/canvas/callback?code=canvas-auth-code&state={state_token}",
                follow_redirects=False,
            )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["provider"] == "canvas"
        assert data["status"] == "connected"
        assert data["institution_id"] == inst.id

    def test_callback_invalid_state_returns_400(self, client):
        """GET /api/lms/canvas/callback with an invalid state must return 400."""
        resp = client.get(
            "/api/lms/canvas/callback?code=anything&state=completely-invalid-state-xyz",
            follow_redirects=False,
        )
        assert resp.status_code == 400
