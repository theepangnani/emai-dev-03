"""Tests for the Brightspace OAuth2 service and LMSProvider adapter (#24/#25).

Tests cover:
  - BrightspaceOAuthClient: auth URL generation, code exchange, token refresh
  - BrightspaceAPIClient: courses, assignments, materials, grades, announcements
  - BrightspaceAdapter: sync_courses, sync_assignments, sync_materials, sync_grades
  - OAuth2 flow endpoints: /api/lms/brightspace/connect, /callback, /refresh
  - Registry: BrightspaceAdapter registered and discoverable

Dependencies:
  - pytest-asyncio for async test support
  - unittest.mock for patching httpx calls (no external network required)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from conftest import PASSWORD
from app.services.brightspace import BrightspaceOAuthClient, BrightspaceAPIClient
from app.services.lms_registry import BrightspaceAdapter, get_provider, list_providers


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_institution(
    base_url: str = "https://test.brightspace.com",
    client_id: str = "test-client-id",
    client_secret: str = "test-client-secret",
) -> MagicMock:
    """Create a mock LMSInstitution with metadata_json OAuth credentials."""
    inst = MagicMock()
    inst.id = 42
    inst.base_url = base_url
    inst.provider = "brightspace"
    inst.is_active = True
    inst.metadata_json = json.dumps(
        {"client_id": client_id, "client_secret": client_secret}
    )
    return inst


def _make_connection(
    institution=None,
    access_token: str = "fake-access-token",
    refresh_token: str = "fake-refresh-token",
) -> MagicMock:
    """Create a mock LMSConnection."""
    conn = MagicMock()
    conn.id = 99
    conn.user_id = 1
    conn.provider = "brightspace"
    conn.institution = institution or _make_institution()
    conn.institution_id = 42
    conn.access_token_enc = access_token
    conn.refresh_token_enc = refresh_token
    conn.status = "connected"
    conn.sync_error = None
    return conn


# ---------------------------------------------------------------------------
# BrightspaceOAuthClient tests
# ---------------------------------------------------------------------------


class TestBrightspaceOAuthClient:

    def test_generate_auth_url_includes_institution_base_url(self):
        """Auth URL must start with the institution's base_url."""
        inst = _make_institution(base_url="https://tdsb.brightspace.com")
        client = BrightspaceOAuthClient()
        url = client.generate_auth_url(inst, "https://app.example.com/callback", "mystate")

        assert url.startswith("https://tdsb.brightspace.com")

    def test_generate_auth_url_includes_client_id(self):
        """Auth URL must contain the OAuth client_id from institution metadata."""
        inst = _make_institution(client_id="special-client-id")
        client = BrightspaceOAuthClient()
        url = client.generate_auth_url(inst, "https://app.example.com/callback", "mystate")

        assert "special-client-id" in url

    def test_generate_auth_url_includes_state(self):
        """Auth URL must include the state parameter for CSRF protection."""
        inst = _make_institution()
        client = BrightspaceOAuthClient()
        url = client.generate_auth_url(inst, "https://app.example.com/callback", "csrf-token-123")

        assert "csrf-token-123" in url

    def test_generate_auth_url_includes_redirect_uri(self):
        """Auth URL must include the redirect_uri parameter."""
        inst = _make_institution()
        client = BrightspaceOAuthClient()
        url = client.generate_auth_url(
            inst, "https://app.example.com/cb", "state"
        )

        assert "redirect_uri" in url

    def test_generate_auth_url_includes_response_type_code(self):
        """Auth URL must request response_type=code for Authorization Code flow."""
        inst = _make_institution()
        client = BrightspaceOAuthClient()
        url = client.generate_auth_url(inst, "https://example.com/cb", "s")

        assert "response_type=code" in url

    @pytest.mark.asyncio
    async def test_exchange_code_returns_tokens(self):
        """exchange_code must return access_token, refresh_token, and expires_in."""
        inst = _make_institution()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            oauth = BrightspaceOAuthClient()
            result = await oauth.exchange_code(inst, "auth-code-abc", "https://example.com/cb")

        assert result["access_token"] == "new-access-token"
        assert result["refresh_token"] == "new-refresh-token"
        assert result["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_refresh_access_token_returns_new_tokens(self):
        """refresh_access_token must call the token endpoint and return new tokens."""
        inst = _make_institution()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "refreshed-access-token",
            "refresh_token": "refreshed-refresh-token",
            "expires_in": 7200,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            oauth = BrightspaceOAuthClient()
            result = await oauth.refresh_access_token(inst, "old-refresh-token")

        assert result["access_token"] == "refreshed-access-token"
        assert result["expires_in"] == 7200

    def test_get_client_id_from_metadata_json(self):
        """_get_client_id must extract value from metadata_json."""
        inst = _make_institution(client_id="extracted-id")
        result = BrightspaceOAuthClient._get_client_id(inst)
        assert result == "extracted-id"

    def test_get_client_secret_from_metadata_json(self):
        """_get_client_secret must extract value from metadata_json."""
        inst = _make_institution(client_secret="extracted-secret")
        result = BrightspaceOAuthClient._get_client_secret(inst)
        assert result == "extracted-secret"

    def test_get_client_id_no_metadata_returns_empty(self):
        """_get_client_id returns empty string when metadata_json is None."""
        inst = MagicMock()
        inst.metadata_json = None
        result = BrightspaceOAuthClient._get_client_id(inst)
        assert result == ""


# ---------------------------------------------------------------------------
# BrightspaceAPIClient tests
# ---------------------------------------------------------------------------


class TestBrightspaceAPIClient:

    def _make_mock_response(self, json_data):
        resp = MagicMock()
        resp.json.return_value = json_data
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        return resp

    @pytest.mark.asyncio
    async def test_get_courses_returns_items(self):
        """get_courses must return a list of enrollment Items from the API."""
        items = [
            {"OrgUnit": {"Id": 1001, "Name": "Math 101", "Type": {"Id": 3}}},
            {"OrgUnit": {"Id": 1002, "Name": "Science 201", "Type": {"Id": 3}}},
        ]
        mock_resp = self._make_mock_response(
            {"Items": items, "PagingInfo": {"HasMoreItems": False}}
        )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            api = BrightspaceAPIClient("https://test.brightspace.com", "token")
            result = await api.get_courses()

        assert len(result) == 2
        assert result[0]["OrgUnit"]["Name"] == "Math 101"

    @pytest.mark.asyncio
    async def test_get_assignments_returns_folders(self):
        """get_assignments must return dropbox folder objects."""
        folders = [
            {"Id": 201, "Name": "Essay 1", "CompletionDate": "2026-04-01T23:59:00Z"},
            {"Id": 202, "Name": "Lab Report", "CompletionDate": None},
        ]
        mock_resp = self._make_mock_response({"Objects": folders})

        with patch("httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            api = BrightspaceAPIClient("https://test.brightspace.com", "token")
            result = await api.get_assignments(1001)

        assert len(result) == 2
        assert result[0]["Name"] == "Essay 1"


# ---------------------------------------------------------------------------
# BrightspaceAdapter tests
# ---------------------------------------------------------------------------


class TestBrightspaceAdapterRegistered:
    """Verify the adapter is registered in the provider registry."""

    def test_brightspace_adapter_registered_in_registry(self):
        """BrightspaceAdapter must appear in the global provider registry."""
        from app.services.lms_registry import _REGISTRY
        assert "brightspace" in _REGISTRY

    def test_brightspace_in_list_providers(self):
        """list_providers() must include brightspace."""
        providers = list_providers()
        provider_ids = [p["provider_id"] for p in providers]
        assert "brightspace" in provider_ids

    def test_brightspace_adapter_is_correct_type(self):
        """The registered adapter must be a BrightspaceAdapter instance."""
        from app.services.lms_registry import _REGISTRY
        assert isinstance(_REGISTRY["brightspace"], BrightspaceAdapter)

    def test_brightspace_adapter_metadata(self):
        """BrightspaceAdapter must report correct provider metadata."""
        adapter = BrightspaceAdapter()
        assert adapter.provider_id == "brightspace"
        assert adapter.display_name == "D2L Brightspace"
        assert adapter.supports_oauth is True
        assert adapter.requires_institution_url is True


# ---------------------------------------------------------------------------
# BrightspaceAdapter sync method tests
# ---------------------------------------------------------------------------


class TestBrightspaceAdapterSync:

    @pytest.mark.asyncio
    async def test_sync_courses_maps_org_unit_to_course(self):
        """sync_courses must create Course records from enrollment OrgUnit data."""
        from app.services.lms_registry import BrightspaceAdapter
        from app.models.course import Course

        enrollments = [
            {"OrgUnit": {"Id": 1001, "Name": "Biology 101"}},
            {"OrgUnit": {"Id": 1002, "Name": "Chemistry 201"}},
        ]

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        added_courses: list = []

        def fake_add(obj):
            obj.id = len(added_courses) + 1
            added_courses.append(obj)

        db.add = fake_add
        db.commit = MagicMock()
        db.refresh = MagicMock()

        connection = _make_connection()

        with patch(
            "app.services.brightspace.BrightspaceAPIClient.get_courses",
            new_callable=AsyncMock,
            return_value=enrollments,
        ):
            adapter = BrightspaceAdapter()
            result = await adapter.sync_courses(connection, db)

        assert len(result) == 2
        course_names = [c.name for c in result]
        assert "Biology 101" in course_names
        assert "Chemistry 201" in course_names
        assert all(c.lms_provider == "brightspace" for c in result)

    @pytest.mark.asyncio
    async def test_sync_courses_sets_lms_external_id(self):
        """sync_courses must set lms_external_id to the orgUnitId string."""
        enrollments = [{"OrgUnit": {"Id": 5555, "Name": "Test Course"}}]

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        added: list = []

        def fake_add(obj):
            obj.id = 1
            added.append(obj)

        db.add = fake_add
        db.commit = MagicMock()
        db.refresh = MagicMock()

        connection = _make_connection()

        with patch(
            "app.services.brightspace.BrightspaceAPIClient.get_courses",
            new_callable=AsyncMock,
            return_value=enrollments,
        ):
            adapter = BrightspaceAdapter()
            await adapter.sync_courses(connection, db)

        assert added[0].lms_external_id == "5555"

    @pytest.mark.asyncio
    async def test_sync_assignments_maps_dropbox_folders(self):
        """sync_assignments must create Assignment records from dropbox folders."""
        from app.services.lms_registry import BrightspaceAdapter
        from app.models.assignment import Assignment
        from app.models.course import Course

        folders = [
            {"Id": 301, "Name": "Homework 1", "CompletionDate": "2026-05-01T23:59:00Z"},
            {"Id": 302, "Name": "Homework 2", "CompletionDate": None},
        ]

        mock_course = MagicMock()
        mock_course.id = 10
        mock_course.lms_external_id = "1001"

        db = MagicMock()
        # query for courses returns our mock course
        db.query.return_value.filter.return_value.all.return_value = [mock_course]
        # query for existing assignments returns None (new records)
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
            "app.services.brightspace.BrightspaceAPIClient.get_assignments",
            new_callable=AsyncMock,
            return_value=folders,
        ):
            adapter = BrightspaceAdapter()
            result = await adapter.sync_assignments(connection, db)

        assert len(result) == 2
        titles = [a.title for a in result]
        assert "Homework 1" in titles
        assert "Homework 2" in titles

    @pytest.mark.asyncio
    async def test_sync_materials_flattens_toc_modules(self):
        """sync_materials must flatten nested TOC modules to leaf topics."""
        from app.services.lms_registry import BrightspaceAdapter

        modules = [
            {
                "Title": "Week 1",
                "Topics": [
                    {"Id": 401, "Title": "Lecture 1 Notes", "Url": "/content/401"},
                    {"Id": 402, "Title": "Reading PDF", "Url": "/content/402.pdf"},
                ],
                "Modules": [
                    {
                        "Title": "Sub-module",
                        "Topics": [
                            {"Id": 403, "Title": "Nested Topic", "Url": "/content/403"},
                        ],
                        "Modules": [],
                    }
                ],
            }
        ]

        mock_course = MagicMock()
        mock_course.id = 10
        mock_course.lms_external_id = "1001"

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
            "app.services.brightspace.BrightspaceAPIClient.get_course_content",
            new_callable=AsyncMock,
            return_value=modules,
        ):
            adapter = BrightspaceAdapter()
            result = await adapter.sync_materials(connection, db)

        # 2 topics from Week 1 + 1 from sub-module = 3 total
        assert len(result) == 3
        titles = {m.title for m in result}
        assert "Lecture 1 Notes" in titles
        assert "Nested Topic" in titles

    @pytest.mark.asyncio
    async def test_sync_grades_updates_assignment_grade(self):
        """sync_grades must update Assignment.max_points when a grade entry matches."""
        from app.services.lms_registry import BrightspaceAdapter

        grade_entries = [
            {"GradeObjectId": 301, "PointsNumerator": 88.0},
        ]

        mock_course = MagicMock()
        mock_course.id = 10
        mock_course.lms_external_id = "1001"

        mock_assignment = MagicMock()
        mock_assignment.lms_external_id = "301"
        mock_assignment.max_points = None

        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [mock_course]
        db.query.return_value.filter.return_value.first.return_value = mock_assignment
        db.commit = MagicMock()

        connection = _make_connection()

        with patch(
            "app.services.brightspace.BrightspaceAPIClient.get_grades",
            new_callable=AsyncMock,
            return_value=grade_entries,
        ):
            adapter = BrightspaceAdapter()
            await adapter.sync_grades(connection, db)

        assert mock_assignment.max_points == 88.0
        db.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Helper method unit tests
# ---------------------------------------------------------------------------


class TestBrightspaceAdapterHelpers:

    def test_parse_completion_date_valid_iso(self):
        """_parse_completion_date must parse a valid ISO 8601 string."""
        adapter = BrightspaceAdapter()
        result = adapter._parse_completion_date("2026-04-15T23:59:00Z")
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 15

    def test_parse_completion_date_none_returns_none(self):
        """_parse_completion_date must return None for None input."""
        adapter = BrightspaceAdapter()
        assert adapter._parse_completion_date(None) is None

    def test_parse_completion_date_empty_returns_none(self):
        """_parse_completion_date must return None for empty string."""
        adapter = BrightspaceAdapter()
        assert adapter._parse_completion_date("") is None

    def test_flatten_modules_handles_empty(self):
        """_flatten_modules must return empty list for empty input."""
        result = BrightspaceAdapter._flatten_modules([])
        assert result == []

    def test_flatten_modules_single_level(self):
        """_flatten_modules must return topics from a single-level module list."""
        modules = [
            {
                "Title": "Module 1",
                "Topics": [{"Id": 1, "Title": "T1"}, {"Id": 2, "Title": "T2"}],
                "Modules": [],
            }
        ]
        result = BrightspaceAdapter._flatten_modules(modules)
        assert len(result) == 2

    def test_detect_content_type_pdf(self):
        """_detect_content_type must classify a .pdf URL as 'notes'."""
        topic = {"Id": 1, "Title": "Notes", "Url": "/content/lecture.pdf"}
        result = BrightspaceAdapter._detect_content_type(topic)
        assert result == "notes"

    def test_detect_content_type_external_link(self):
        """_detect_content_type must classify an external URL as 'resources'."""
        topic = {"Id": 2, "Title": "Link", "TypeIdentifier": "Link", "Url": "https://example.com"}
        result = BrightspaceAdapter._detect_content_type(topic)
        assert result == "resources"


# ---------------------------------------------------------------------------
# OAuth2 endpoint tests (integration — uses TestClient)
# ---------------------------------------------------------------------------


class TestBrightspaceOAuthEndpoints:

    def test_connect_endpoint_redirects_to_brightspace(self, client, db_session):
        """GET /api/lms/brightspace/connect must redirect to Brightspace OAuth URL."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        # Create user + institution
        email = "brightspace_connect@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                full_name="BS Connect Test",
                role=UserRole.STUDENT,
                hashed_password=get_password_hash(PASSWORD),
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        inst = LMSInstitution(
            name="Test Board",
            provider="brightspace",
            base_url="https://test.brightspace.com",
            is_active=True,
            metadata_json=json.dumps({"client_id": "ci", "client_secret": "cs"}),
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
            f"/api/lms/brightspace/connect?institution_id={inst.id}",
            headers=headers,
            follow_redirects=False,
        )

        assert resp.status_code == 302
        location = resp.headers.get("location", "")
        assert "test.brightspace.com" in location

    def test_connect_endpoint_invalid_institution_returns_404(self, client, db_session):
        """GET /api/lms/brightspace/connect with unknown institution_id must return 404."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        email = "bs_404_test@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                full_name="BS 404",
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
            "/api/lms/brightspace/connect?institution_id=999999",
            headers=headers,
            follow_redirects=False,
        )
        assert resp.status_code == 404

    def test_callback_creates_lms_connection(self, client, db_session):
        """GET /api/lms/brightspace/callback must create an LMSConnection on success."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.api.routes.lms_connections import _brightspace_oauth_state

        email = "bs_callback@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                full_name="BS Callback",
                role=UserRole.STUDENT,
                hashed_password=get_password_hash(PASSWORD),
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        inst = LMSInstitution(
            name="Callback Test Board",
            provider="brightspace",
            base_url="https://callback.brightspace.com",
            is_active=True,
            metadata_json=json.dumps({"client_id": "ci2", "client_secret": "cs2"}),
        )
        db_session.add(inst)
        db_session.commit()
        db_session.refresh(inst)

        # Seed state as if /connect was called
        state_token = "test-state-token-callback-abc"
        _brightspace_oauth_state[state_token] = {
            "user_id": user.id,
            "institution_id": inst.id,
        }

        with patch(
            "app.api.routes.lms_connections.BrightspaceOAuthClient"
        ) as MockOAuth:
            mock_instance = AsyncMock()
            mock_instance.exchange_code = AsyncMock(
                return_value={
                    "access_token": "at-from-callback",
                    "refresh_token": "rt-from-callback",
                    "expires_in": 3600,
                }
            )
            MockOAuth.return_value = mock_instance

            resp = client.get(
                f"/api/lms/brightspace/callback?code=authcode123&state={state_token}",
                follow_redirects=False,
            )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["provider"] == "brightspace"
        assert data["status"] == "connected"
        assert data["institution_id"] == inst.id

    def test_callback_invalid_state_returns_400(self, client):
        """GET /api/lms/brightspace/callback with bad state must return 400."""
        resp = client.get(
            "/api/lms/brightspace/callback?code=anything&state=invalid-state-xyz",
            follow_redirects=False,
        )
        assert resp.status_code == 400


# Import needed for endpoint tests
from app.models.lms_institution import LMSInstitution
