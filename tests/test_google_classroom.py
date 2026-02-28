from unittest.mock import patch, MagicMock

import pytest
from conftest import PASSWORD, _login, _auth


@pytest.fixture()
def gc_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "gc_user@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        email=email, full_name="GC User", role=UserRole.TEACHER,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ── Status endpoint ───────────────────────────────────────────

class TestGoogleStatus:
    def test_not_connected_by_default(self, client, gc_user):
        headers = _auth(client, gc_user.email)
        resp = client.get("/api/google/status", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["connected"] is False

    def test_unauthenticated_returns_401(self, client):
        resp = client.get("/api/google/status")
        assert resp.status_code == 401


# ── Disconnect endpoint ──────────────────────────────────────

class TestGoogleDisconnect:
    def test_disconnect_clears_tokens(self, client, gc_user, db_session):
        # Simulate connected state
        gc_user.google_id = "google123"
        gc_user.google_access_token = "fake-access-token"
        gc_user.google_refresh_token = "fake-refresh-token"
        db_session.commit()

        headers = _auth(client, gc_user.email)
        resp = client.delete("/api/google/disconnect", headers=headers)
        assert resp.status_code == 200
        assert "disconnected" in resp.json()["message"].lower()

        # Verify status is now disconnected
        status_resp = client.get("/api/google/status", headers=headers)
        assert status_resp.json()["connected"] is False


# ── Courses without connection ────────────────────────────────

class TestGoogleCoursesNoConnection:
    def test_courses_without_connection_returns_400(self, client, gc_user):
        headers = _auth(client, gc_user.email)
        resp = client.get("/api/google/courses", headers=headers)
        assert resp.status_code == 400
        assert "not connected" in resp.json()["detail"].lower()

    def test_sync_without_connection_returns_400(self, client, gc_user):
        headers = _auth(client, gc_user.email)
        resp = client.post("/api/google/courses/sync", headers=headers)
        assert resp.status_code == 400
        assert "not connected" in resp.json()["detail"].lower()


# ── Auth endpoint ─────────────────────────────────────────────

class TestGoogleAuth:
    def test_auth_returns_authorization_url(self, client):
        resp = client.get("/api/google/auth")
        assert resp.status_code == 200
        data = resp.json()
        assert "authorization_url" in data
        assert "state" in data


# ── Sync response format (#433) ──────────────────────────────

class TestSyncResponseFormat:
    """Test that course sync returns material/assignment counts."""

    def _make_student_user(self, db_session):
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.models.student import Student

        email = "sync_student@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email, full_name="Sync Student", role=UserRole.STUDENT,
                hashed_password=get_password_hash(PASSWORD),
                google_access_token="fake-access",
                google_refresh_token="fake-refresh",
            )
            db_session.add(user)
            db_session.flush()
            student = Student(user_id=user.id)
            db_session.add(student)
            db_session.commit()
            db_session.refresh(user)
        return user

    @patch("app.api.routes.google_classroom.list_courses")
    @patch("app.api.routes.google_classroom.get_course_work_materials")
    @patch("app.api.routes.google_classroom.get_course_work")
    def test_sync_returns_material_and_assignment_counts(
        self, mock_coursework, mock_materials, mock_courses, client, db_session
    ):
        user = self._make_student_user(db_session)
        creds = MagicMock()
        creds.token = "fake-access"
        creds.refresh_token = "fake-refresh"

        mock_courses.return_value = (
            [{"id": "gc-100", "name": "Test Course", "description": "desc"}],
            creds,
        )
        mock_materials.return_value = (
            [{"id": "mat-1", "title": "Material 1", "state": "PUBLISHED"}],
            creds,
        )
        mock_coursework.return_value = (
            [{"id": "cw-1", "title": "Assignment 1"}],
            creds,
        )

        headers = _auth(client, user.email)
        resp = client.post("/api/google/courses/sync", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "materials_synced" in data
        assert "assignments_synced" in data
        assert data["materials_synced"] >= 0
        assert data["assignments_synced"] >= 0
        assert "course" in data["message"].lower()

    @patch("app.api.routes.google_classroom.list_courses")
    @patch("app.api.routes.google_classroom.get_course_work_materials")
    @patch("app.api.routes.google_classroom.get_course_work")
    def test_sync_message_includes_counts_when_nonzero(
        self, mock_coursework, mock_materials, mock_courses, client, db_session
    ):
        user = self._make_student_user(db_session)
        creds = MagicMock()
        creds.token = "fake-access"
        creds.refresh_token = "fake-refresh"

        mock_courses.return_value = (
            [{"id": "gc-200", "name": "New Course"}],
            creds,
        )
        mock_materials.return_value = (
            [{"id": "mat-new-1", "title": "New Mat", "state": "PUBLISHED"}],
            creds,
        )
        mock_coursework.return_value = (
            [{"id": "cw-new-1", "title": "New Assignment"}],
            creds,
        )

        headers = _auth(client, user.email)
        resp = client.post("/api/google/courses/sync", headers=headers)
        data = resp.json()
        # The message should mention materials and assignments when new ones are synced
        if data["materials_synced"] > 0:
            assert "material" in data["message"].lower()
        if data["assignments_synced"] > 0:
            assert "assignment" in data["message"].lower()


# ── Background sync job (#434) ────────────────────────────────

class TestBackgroundGoogleSync:
    """Test the background Google Classroom sync job."""

    @patch("app.api.routes.google_classroom.list_courses")
    @patch("app.api.routes.google_classroom.get_course_work_materials")
    @patch("app.api.routes.google_classroom.get_course_work")
    def test_sync_job_processes_connected_users(
        self, mock_coursework, mock_materials, mock_courses, db_session
    ):
        import asyncio
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.jobs.google_sync import sync_google_classrooms

        email = "bg_sync_user@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email, full_name="BG Sync User", role=UserRole.STUDENT,
                hashed_password=get_password_hash(PASSWORD),
                google_access_token="fake-bg-access",
                google_refresh_token="fake-bg-refresh",
            )
            db_session.add(user)
            db_session.commit()

        creds = MagicMock()
        creds.token = "fake-bg-access"
        creds.refresh_token = "fake-bg-refresh"

        mock_courses.return_value = (
            [{"id": "gc-bg-1", "name": "BG Course"}],
            creds,
        )
        mock_materials.return_value = ([], creds)
        mock_coursework.return_value = ([], creds)

        # Should not raise
        asyncio.run(sync_google_classrooms())

    @patch("app.api.routes.google_classroom.list_courses")
    def test_sync_job_handles_token_failure_gracefully(
        self, mock_courses, db_session
    ):
        import asyncio
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.jobs.google_sync import sync_google_classrooms

        email = "bg_fail_user@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email, full_name="BG Fail User", role=UserRole.STUDENT,
                hashed_password=get_password_hash(PASSWORD),
                google_access_token="expired-token",
                google_refresh_token="bad-refresh",
            )
            db_session.add(user)
            db_session.commit()

        mock_courses.side_effect = Exception("Token expired")

        # Should not raise — failed users are logged, not propagated
        asyncio.run(sync_google_classrooms())
