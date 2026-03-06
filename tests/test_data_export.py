"""Tests for the data export feature (PIPEDA Right of Access)."""
import os
import uuid

import pytest

from tests.conftest import PASSWORD, _auth, _login


def _unique_email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


@pytest.fixture()
def parent_email():
    return _unique_email("export_parent")


@pytest.fixture()
def student_email():
    return _unique_email("export_student")


@pytest.fixture()
def parent_user(client, db_session, parent_email):
    """Create a parent user for testing."""
    resp = client.post("/api/auth/register", json={
        "email": parent_email,
        "password": PASSWORD,
        "full_name": "Export Parent",
        "role": "parent",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture()
def student_user(client, db_session, student_email):
    """Create a student user for testing."""
    resp = client.post("/api/auth/register", json={
        "email": student_email,
        "password": PASSWORD,
        "full_name": "Export Student",
        "role": "student",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestDataExportEndpoints:
    """Test data export API endpoints."""

    def test_request_export(self, client, parent_user, parent_email):
        """POST /api/users/me/export creates an export request."""
        headers = _auth(client, parent_email)
        resp = client.post("/api/users/me/export", headers=headers)
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] in ("pending", "processing", "completed")
        assert data["id"] is not None
        assert data["created_at"] is not None

    def test_request_export_completes(self, client, parent_user, parent_email):
        """Export request processes and reaches completed status."""
        headers = _auth(client, parent_email)
        resp = client.post("/api/users/me/export", headers=headers)
        assert resp.status_code == 202
        data = resp.json()
        # Synchronous processing — should complete immediately
        assert data["status"] == "completed"
        assert data["download_url"] is not None
        assert data["expires_at"] is not None

    def test_list_exports(self, client, parent_user, parent_email):
        """GET /api/users/me/exports returns export history."""
        headers = _auth(client, parent_email)
        # Create an export first
        client.post("/api/users/me/export", headers=headers)
        resp = client.get("/api/users/me/exports", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["status"] in ("pending", "processing", "completed")

    def test_download_export(self, client, parent_user, parent_email):
        """GET /api/users/me/exports/{token}/download returns a ZIP file."""
        headers = _auth(client, parent_email)
        resp = client.post("/api/users/me/export", headers=headers)
        assert resp.status_code == 202
        data = resp.json()
        assert data["download_url"] is not None

        # Download using the URL
        download_resp = client.get(data["download_url"], headers=headers)
        assert download_resp.status_code == 200
        assert download_resp.headers["content-type"] == "application/zip"
        assert "classbridge_data_export" in download_resp.headers.get("content-disposition", "")

    def test_download_invalid_token(self, client, parent_user, parent_email):
        """Downloading with invalid token returns 404."""
        headers = _auth(client, parent_email)
        resp = client.get("/api/users/me/exports/invalid-token/download", headers=headers)
        assert resp.status_code == 404

    def test_export_requires_auth(self, client):
        """Export endpoints require authentication."""
        resp = client.post("/api/users/me/export")
        assert resp.status_code == 401

        resp = client.get("/api/users/me/exports")
        assert resp.status_code == 401

    def test_student_export(self, client, student_user, student_email):
        """Student users can also request data export."""
        headers = _auth(client, student_email)
        resp = client.post("/api/users/me/export", headers=headers)
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "completed"

    def test_export_zip_contains_expected_files(self, client, parent_user, parent_email):
        """Completed export ZIP contains expected JSON data files."""
        import zipfile
        import io

        headers = _auth(client, parent_email)
        resp = client.post("/api/users/me/export", headers=headers)
        assert resp.status_code == 202
        data = resp.json()

        download_resp = client.get(data["download_url"], headers=headers)
        assert download_resp.status_code == 200

        with zipfile.ZipFile(io.BytesIO(download_resp.content)) as zf:
            names = zf.namelist()
            assert "export_metadata.json" in names
            assert "profile.json" in names

    def test_cannot_download_other_users_export(self, client, parent_user, student_user, parent_email, student_email):
        """Users cannot download exports belonging to other users."""
        # Parent creates an export
        parent_headers = _auth(client, parent_email)
        resp = client.post("/api/users/me/export", headers=parent_headers)
        data = resp.json()

        # Extract token from download URL
        download_url = data["download_url"]
        token = download_url.split("/exports/")[1].split("/download")[0]

        # Student tries to download it
        student_headers = _auth(client, student_email)
        resp = client.get(f"/api/users/me/exports/{token}/download", headers=student_headers)
        assert resp.status_code == 404


class TestDataExportService:
    """Test the data export service directly."""

    def test_export_contains_user_profile(self, client, parent_user, parent_email, db_session):
        """Generated export includes user profile data."""
        import json
        import zipfile
        import io

        headers = _auth(client, parent_email)
        resp = client.post("/api/users/me/export", headers=headers)
        data = resp.json()

        download_resp = client.get(data["download_url"], headers=headers)
        with zipfile.ZipFile(io.BytesIO(download_resp.content)) as zf:
            profile = json.loads(zf.read("profile.json"))
            assert profile["email"] == parent_email
            assert profile["full_name"] == "Export Parent"

    def test_cleanup_expired_exports(self, db_session):
        """Expired exports are cleaned up."""
        from datetime import datetime, timedelta, timezone
        from app.services.data_export_service import cleanup_expired_exports
        from app.models.data_export import DataExportRequest

        # Create an expired export request
        token = f"expired-test-token-{uuid.uuid4().hex[:12]}"
        export = DataExportRequest(
            user_id=1,
            status="completed",
            download_token=token,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(export)
        db_session.commit()

        count = cleanup_expired_exports(db_session)
        assert count >= 1

        db_session.refresh(export)
        assert export.status == "expired"
