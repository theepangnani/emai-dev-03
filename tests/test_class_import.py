"""Tests for CB-ONBOARD-001 class-import endpoints (#3985).

Covers:
  - GET  /api/courses/google-classroom/preview
  - POST /api/courses/parse-screenshot
  - POST /api/courses/bulk
"""
from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def ci_user(db_session):
    """A plain parent user we can log in as."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "ci_parent@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        email=email,
        full_name="Class Import Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def ci_user_connected(db_session):
    """A user whose Google OAuth state is populated (classroom scope granted)."""
    from app.core.encryption import encrypt_token
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "ci_parent_gc@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        email=email,
        full_name="Connected Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
        google_access_token=encrypt_token("fake-access-token"),
        google_refresh_token=encrypt_token("fake-refresh-token"),
        google_granted_scopes=(
            "https://www.googleapis.com/auth/classroom.courses.readonly,"
            "https://www.googleapis.com/auth/classroom.rosters.readonly"
        ),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ── GET /google-classroom/preview ────────────────────────────────


class TestGoogleClassroomPreview:
    def test_not_connected_returns_cta(self, client, ci_user):
        headers = _auth(client, ci_user.email)
        resp = client.get(
            "/api/courses/google-classroom/preview", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False
        assert data["connect_url"] == "/api/google/auth"
        assert data["courses"] == []

    def test_requires_auth(self, client):
        resp = client.get("/api/courses/google-classroom/preview")
        assert resp.status_code == 401

    @patch("app.api.routes.class_import.list_course_teachers")
    @patch("app.api.routes.class_import.list_courses")
    def test_connected_returns_courses_with_existing_flag(
        self, mock_list_courses, mock_list_teachers, client, ci_user_connected, db_session
    ):
        from app.models.course import Course

        # Pre-create a course with google_classroom_id "gc-dup" so the response
        # can detect existing=true for that row.
        existing = Course(
            name="Already Imported",
            google_classroom_id="gc-dup",
            created_by_user_id=ci_user_connected.id,
            is_private=True,
        )
        db_session.add(existing)
        db_session.commit()

        mock_list_courses.return_value = (
            [
                {"id": "gc-100", "name": "Grade 8 FI", "section": "8 FI"},
                {"id": "gc-dup", "name": "Already Imported", "section": None},
            ],
            MagicMock(),
        )

        def _teachers_side_effect(access_token, course_id, refresh_token=None):
            if course_id == "gc-100":
                return (
                    [
                        {
                            "profile": {
                                "name": {"fullName": "Melanie Schmidt"},
                                "emailAddress": "melanie@board.edu",
                            }
                        }
                    ],
                    MagicMock(),
                )
            return ([], MagicMock())

        mock_list_teachers.side_effect = _teachers_side_effect

        headers = _auth(client, ci_user_connected.email)
        resp = client.get(
            "/api/courses/google-classroom/preview", headers=headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["connected"] is True
        assert data.get("error") is None
        courses = {c["google_classroom_id"]: c for c in data["courses"]}
        assert set(courses) == {"gc-100", "gc-dup"}
        assert courses["gc-100"]["teacher_name"] == "Melanie Schmidt"
        assert courses["gc-100"]["teacher_email"] == "melanie@board.edu"
        assert courses["gc-100"]["existing"] is False
        assert courses["gc-dup"]["existing"] is True
        assert courses["gc-dup"]["existing_course_id"] == existing.id

    @patch(
        "app.api.routes.class_import.list_courses",
        side_effect=RuntimeError("google api down"),
    )
    def test_google_api_error_returns_graceful_200(
        self, _mock_list, client, ci_user_connected
    ):
        headers = _auth(client, ci_user_connected.email)
        resp = client.get(
            "/api/courses/google-classroom/preview", headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert "temporarily unavailable" in (data.get("error") or "").lower()
        assert data["courses"] == []

    @patch("app.api.routes.class_import.list_course_teachers")
    @patch("app.api.routes.class_import.list_courses")
    def test_partial_teacher_fetch_failure_is_tolerated(
        self,
        mock_list_courses,
        mock_list_teachers,
        client,
        ci_user_connected,
    ):
        """One failing list_course_teachers call must not abort the preview;
        both courses must still come back (failing one with None teacher)."""
        mock_list_courses.return_value = (
            [
                {"id": "gc-ok", "name": "OK Class", "section": None},
                {"id": "gc-boom", "name": "Boom Class", "section": None},
            ],
            MagicMock(),
        )

        def _teachers_side_effect(access_token, course_id, refresh_token=None):
            if course_id == "gc-boom":
                raise RuntimeError("teacher roster failed")
            return (
                [
                    {
                        "profile": {
                            "name": {"fullName": "Ms OK"},
                            "emailAddress": "ok@board.edu",
                        }
                    }
                ],
                MagicMock(),
            )

        mock_list_teachers.side_effect = _teachers_side_effect

        headers = _auth(client, ci_user_connected.email)
        resp = client.get(
            "/api/courses/google-classroom/preview", headers=headers
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["connected"] is True
        courses = {c["google_classroom_id"]: c for c in data["courses"]}
        assert set(courses) == {"gc-ok", "gc-boom"}
        assert courses["gc-ok"]["teacher_name"] == "Ms OK"
        assert courses["gc-ok"]["teacher_email"] == "ok@board.edu"
        assert courses["gc-boom"]["teacher_name"] is None
        assert courses["gc-boom"]["teacher_email"] is None


# ── POST /parse-screenshot ───────────────────────────────────────


def _fake_vision_message(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    msg = MagicMock()
    msg.content = [block]
    return msg


class TestParseScreenshot:
    def _png_bytes(self) -> bytes:
        # 1×1 transparent PNG
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00"
            b"\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx"
            b"\x9cc\xfa\xcf\x00\x00\x00\x02\x00\x01\xe5\x27\xde\xfc\x00\x00\x00"
            b"\x00IEND\xaeB`\x82"
        )

    @patch("app.services.class_import_service.get_anthropic_client")
    def test_happy_path_returns_parsed_rows(
        self, mock_client_factory, client, ci_user
    ):
        fake_output = json.dumps(
            [
                {
                    "class_name": "GRADE 8 FI Schmidt",
                    "section": "8 FI",
                    "teacher_name": "melanie schmidt",
                },
                {
                    "class_name": "Intermediate Band",
                    "section": None,
                    "teacher_name": "J. Lee",
                },
            ]
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = _fake_vision_message(
            fake_output
        )
        mock_client_factory.return_value = fake_client

        headers = _auth(client, ci_user.email)
        resp = client.post(
            "/api/courses/parse-screenshot",
            headers=headers,
            files={"image": ("gc.png", self._png_bytes(), "image/png")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["parsed"]) == 2
        assert data["parsed"][0]["class_name"] == "GRADE 8 FI Schmidt"
        assert data["parsed"][0]["section"] == "8 FI"
        assert data["parsed"][0]["teacher_name"] == "melanie schmidt"
        assert data["parsed"][0]["teacher_email"] is None
        assert data["parsed"][1]["section"] is None

    @patch("app.services.class_import_service.get_anthropic_client")
    def test_strips_code_fences(self, mock_client_factory, client, ci_user):
        fake_output = (
            "```json\n"
            '[{"class_name": "X", "section": null, "teacher_name": "Y"}]\n'
            "```"
        )
        fake_client = MagicMock()
        fake_client.messages.create.return_value = _fake_vision_message(
            fake_output
        )
        mock_client_factory.return_value = fake_client

        headers = _auth(client, ci_user.email)
        resp = client.post(
            "/api/courses/parse-screenshot",
            headers=headers,
            files={"image": ("gc.png", self._png_bytes(), "image/png")},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["parsed"][0]["class_name"] == "X"

    @patch("app.services.class_import_service.get_anthropic_client")
    def test_malformed_json_returns_422(
        self, mock_client_factory, client, ci_user
    ):
        fake_client = MagicMock()
        fake_client.messages.create.return_value = _fake_vision_message(
            "this is not JSON"
        )
        mock_client_factory.return_value = fake_client

        headers = _auth(client, ci_user.email)
        resp = client.post(
            "/api/courses/parse-screenshot",
            headers=headers,
            files={"image": ("gc.png", self._png_bytes(), "image/png")},
        )
        assert resp.status_code == 422
        assert "parse" in json.dumps(resp.json()).lower()

    def test_rejects_non_image_content_type(self, client, ci_user):
        headers = _auth(client, ci_user.email)
        resp = client.post(
            "/api/courses/parse-screenshot",
            headers=headers,
            files={
                "image": ("thing.txt", b"hello", "text/plain"),
            },
        )
        assert resp.status_code == 400

    def test_rejects_oversize_upload(self, client, ci_user):
        big = b"\x00" * (10 * 1024 * 1024 + 1)
        headers = _auth(client, ci_user.email)
        resp = client.post(
            "/api/courses/parse-screenshot",
            headers=headers,
            files={"image": ("big.png", io.BytesIO(big), "image/png")},
        )
        assert resp.status_code == 400

    def test_rejects_bad_magic_bytes(self, client, ci_user):
        # Payload labelled image/jpeg but contents are plain bytes — must 400.
        headers = _auth(client, ci_user.email)
        resp = client.post(
            "/api/courses/parse-screenshot",
            headers=headers,
            files={
                "image": (
                    "fake.jpg",
                    b"not really an image, just some text bytes here",
                    "image/jpeg",
                ),
            },
        )
        assert resp.status_code == 400
        assert "jpeg" in resp.text.lower() or "image" in resp.text.lower()

    @patch("app.services.class_import_service.get_anthropic_client")
    def test_generic_vision_exception_returns_422(
        self, mock_client_factory, client, ci_user
    ):
        # A non-ValueError, non-anthropic exception from the vision path
        # still maps to 422 with a friendly detail.
        fake_client = MagicMock()
        fake_client.messages.create.side_effect = RuntimeError("boom")
        mock_client_factory.return_value = fake_client

        headers = _auth(client, ci_user.email)
        resp = client.post(
            "/api/courses/parse-screenshot",
            headers=headers,
            files={"image": ("gc.png", self._png_bytes(), "image/png")},
        )
        assert resp.status_code == 422
        assert "parse" in json.dumps(resp.json()).lower()

    def test_route_is_async(self):
        """Smoke check: the route handler is a coroutine function."""
        import inspect

        from app.api.routes.class_import import parse_screenshot

        assert inspect.iscoroutinefunction(parse_screenshot)


# ── POST /bulk ───────────────────────────────────────────────────


class TestBulkCreate:
    def test_happy_path_creates_courses(self, client, ci_user, db_session):
        headers = _auth(client, ci_user.email)
        resp = client.post(
            "/api/courses/bulk",
            headers=headers,
            json={
                "rows": [
                    {
                        "class_name": "Math 8",
                        "section": "8 FI",
                        "teacher_name": "Mel Schmidt",
                        "teacher_email": None,
                        "google_classroom_id": "gc-bulk-1",
                    },
                    {
                        "class_name": "Art",
                        "section": None,
                        "teacher_name": "J. Lee",
                        "teacher_email": None,
                        "google_classroom_id": "gc-bulk-2",
                    },
                ]
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["created"]) == 2
        assert data["failed"] == []

        # Verify persisted
        from app.models.course import Course

        courses = (
            db_session.query(Course)
            .filter(Course.google_classroom_id.in_(["gc-bulk-1", "gc-bulk-2"]))
            .all()
        )
        assert len(courses) == 2
        # Section is stored in description prefix
        math8 = next(c for c in courses if c.google_classroom_id == "gc-bulk-1")
        assert math8.description == "Section: 8 FI"

    def test_duplicate_gc_id_skipped(self, client, ci_user, db_session):
        from app.models.course import Course

        existing = Course(
            name="Pre-existing",
            google_classroom_id="gc-dupe-bulk",
            created_by_user_id=ci_user.id,
            is_private=True,
        )
        db_session.add(existing)
        db_session.commit()
        existing_id = existing.id

        headers = _auth(client, ci_user.email)
        resp = client.post(
            "/api/courses/bulk",
            headers=headers,
            json={
                "rows": [
                    {
                        "class_name": "Should Skip",
                        "section": None,
                        "teacher_name": "T",
                        "teacher_email": None,
                        "google_classroom_id": "gc-dupe-bulk",
                    }
                ]
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["created"] == []
        assert len(data["failed"]) == 1
        failure = data["failed"][0]
        assert failure["error"] == "already_imported"
        assert failure["existing_course_id"] == existing_id

    def test_empty_rows_rejected(self, client, ci_user):
        headers = _auth(client, ci_user.email)
        resp = client.post(
            "/api/courses/bulk", headers=headers, json={"rows": []}
        )
        assert resp.status_code == 422

    def test_too_many_rows_rejected(self, client, ci_user):
        headers = _auth(client, ci_user.email)
        rows = [
            {
                "class_name": f"Class {i}",
                "section": None,
                "teacher_name": "T",
                "teacher_email": None,
                "google_classroom_id": f"gc-many-{i}",
            }
            for i in range(51)
        ]
        resp = client.post(
            "/api/courses/bulk", headers=headers, json={"rows": rows}
        )
        assert resp.status_code == 422

    def test_partial_success_with_bad_row(self, client, ci_user, db_session):
        """One validation-valid row alongside a duplicate gc_id still persists the good one."""
        from app.models.course import Course

        db_session.add(
            Course(
                name="Dup One",
                google_classroom_id="gc-partial-dup",
                created_by_user_id=ci_user.id,
                is_private=True,
            )
        )
        db_session.commit()

        headers = _auth(client, ci_user.email)
        resp = client.post(
            "/api/courses/bulk",
            headers=headers,
            json={
                "rows": [
                    {
                        "class_name": "Good One",
                        "section": None,
                        "teacher_name": "Mrs G",
                        "teacher_email": None,
                        "google_classroom_id": "gc-partial-good",
                    },
                    {
                        "class_name": "Dup",
                        "section": None,
                        "teacher_name": "Mr D",
                        "teacher_email": None,
                        "google_classroom_id": "gc-partial-dup",
                    },
                ]
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["created"]) == 1
        assert len(data["failed"]) == 1
        assert data["created"][0]["index"] == 0
        assert data["failed"][0]["index"] == 1
        assert data["failed"][0]["error"] == "already_imported"

        persisted = (
            db_session.query(Course)
            .filter(Course.google_classroom_id == "gc-partial-good")
            .first()
        )
        assert persisted is not None
        assert persisted.name == "Good One"

    def test_requires_auth(self, client):
        resp = client.post(
            "/api/courses/bulk",
            json={
                "rows": [
                    {
                        "class_name": "X",
                        "section": None,
                        "teacher_name": "Y",
                        "teacher_email": None,
                        "google_classroom_id": None,
                    }
                ]
            },
        )
        assert resp.status_code == 401

    def test_response_shape_validates_typed_model(
        self, client, ci_user, db_session
    ):
        """The /bulk response body must validate against the typed
        BulkCreateResult Pydantic model (no raw dicts at the boundary)."""
        from app.models.course import Course
        from app.schemas.class_import import (
            BulkCreatedItem,
            BulkCreateResult,
            BulkFailedItem,
        )

        db_session.add(
            Course(
                name="Dup Shape",
                google_classroom_id="gc-shape-dup",
                created_by_user_id=ci_user.id,
                is_private=True,
            )
        )
        db_session.commit()

        headers = _auth(client, ci_user.email)
        resp = client.post(
            "/api/courses/bulk",
            headers=headers,
            json={
                "rows": [
                    {
                        "class_name": "Shape Good",
                        "section": None,
                        "teacher_name": "T",
                        "teacher_email": None,
                        "google_classroom_id": "gc-shape-good",
                    },
                    {
                        "class_name": "Shape Dup",
                        "section": None,
                        "teacher_name": "T",
                        "teacher_email": None,
                        "google_classroom_id": "gc-shape-dup",
                    },
                ]
            },
        )
        assert resp.status_code == 200, resp.text
        # Strict validation — anything extra or missing blows up here.
        parsed = BulkCreateResult.model_validate(resp.json())
        assert all(isinstance(item, BulkCreatedItem) for item in parsed.created)
        assert all(isinstance(item, BulkFailedItem) for item in parsed.failed)
        assert len(parsed.created) == 1
        assert parsed.created[0].name == "Shape Good"
        assert len(parsed.failed) == 1
        assert parsed.failed[0].error == "already_imported"
