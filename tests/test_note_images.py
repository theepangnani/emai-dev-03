import io
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from conftest import PASSWORD, _auth


@pytest.fixture()
def setup(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students

    owner = db_session.query(User).filter(User.email == "imgowner@test.com").first()
    if owner:
        parent = db_session.query(User).filter(User.email == "imgparent@test.com").first()
        outsider = db_session.query(User).filter(User.email == "imgoutsider@test.com").first()
        admin = db_session.query(User).filter(User.email == "imgadmin@test.com").first()
        return {"owner": owner, "parent": parent, "outsider": outsider, "admin": admin}

    hashed = get_password_hash(PASSWORD)
    owner = User(email="imgowner@test.com", full_name="Img Owner", role=UserRole.STUDENT, hashed_password=hashed)
    parent = User(email="imgparent@test.com", full_name="Img Parent", role=UserRole.PARENT, hashed_password=hashed)
    outsider = User(email="imgoutsider@test.com", full_name="Img Outsider", role=UserRole.STUDENT, hashed_password=hashed)
    admin = User(email="imgadmin@test.com", full_name="Img Admin", role=UserRole.ADMIN, hashed_password=hashed)
    db_session.add_all([owner, parent, outsider, admin])
    db_session.flush()

    student_rec = Student(user_id=owner.id)
    db_session.add(student_rec)
    db_session.flush()

    # Link parent to student
    db_session.execute(parent_students.insert().values(
        parent_id=parent.id, student_id=student_rec.id
    ))
    db_session.commit()

    return {"owner": owner, "parent": parent, "outsider": outsider, "admin": admin}


def _make_png_bytes(width=100, height=100, color=(255, 0, 0)):
    """Create a valid PNG image in memory."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def _make_large_bytes(size_mb=6):
    """Create bytes larger than the 5 MB limit."""
    return b"\x00" * (size_mb * 1024 * 1024)


class TestUploadNoteImage:
    @patch("app.api.routes.notes.gcs_upload_file")
    def test_upload_happy_path(self, mock_upload, client, setup):
        mock_upload.return_value = "notes/1/abc.jpg"
        headers = _auth(client, "imgowner@test.com")
        png_bytes = _make_png_bytes()

        resp = client.post(
            "/api/notes/images",
            files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["user_id"] == setup["owner"].id
        assert data["note_id"] is None
        assert data["image_url"].startswith("/api/notes/images/")
        assert data["media_type"] in ("image/png", "image/jpeg")
        assert data["file_size"] > 0
        mock_upload.assert_called_once()

    def test_reject_oversized_file(self, client, setup):
        headers = _auth(client, "imgowner@test.com")
        large_png = _make_png_bytes(width=10, height=10)
        # We need actual bytes > 5MB, so use raw bytes with valid content_type
        large_bytes = _make_large_bytes(6)

        resp = client.post(
            "/api/notes/images",
            files={"file": ("big.png", io.BytesIO(large_bytes), "image/png")},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "too large" in resp.json()["detail"].lower()

    def test_reject_invalid_format(self, client, setup):
        headers = _auth(client, "imgowner@test.com")
        resp = client.post(
            "/api/notes/images",
            files={"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Invalid file type" in resp.json()["detail"]

    def test_reject_unauthenticated(self, client, setup):
        png_bytes = _make_png_bytes()
        resp = client.post(
            "/api/notes/images",
            files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
        )
        assert resp.status_code == 401


class TestServeNoteImage:
    @patch("app.api.routes.notes.gcs_download_file")
    @patch("app.api.routes.notes.gcs_upload_file")
    def test_serve_happy_path(self, mock_upload, mock_download, client, setup):
        mock_upload.return_value = "notes/1/abc.jpg"
        headers = _auth(client, "imgowner@test.com")
        png_bytes = _make_png_bytes()

        # Upload
        upload_resp = client.post(
            "/api/notes/images",
            files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
            headers=headers,
        )
        image_id = upload_resp.json()["id"]

        # Serve
        mock_download.return_value = png_bytes
        resp = client.get(f"/api/notes/images/{image_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "private, max-age=3600"
        assert len(resp.content) > 0

    @patch("app.api.routes.notes.gcs_download_file")
    @patch("app.api.routes.notes.gcs_upload_file")
    def test_outsider_cannot_access(self, mock_upload, mock_download, client, setup):
        mock_upload.return_value = "notes/1/abc.jpg"

        # Owner uploads
        headers_owner = _auth(client, "imgowner@test.com")
        png_bytes = _make_png_bytes()
        upload_resp = client.post(
            "/api/notes/images",
            files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
            headers=headers_owner,
        )
        image_id = upload_resp.json()["id"]

        # Outsider tries to access
        headers_outsider = _auth(client, "imgoutsider@test.com")
        resp = client.get(f"/api/notes/images/{image_id}", headers=headers_outsider)
        assert resp.status_code == 404

    @patch("app.api.routes.notes.gcs_download_file")
    @patch("app.api.routes.notes.gcs_upload_file")
    def test_parent_can_access_child_image(self, mock_upload, mock_download, client, setup):
        mock_upload.return_value = "notes/1/abc.jpg"

        # Owner (child) uploads
        headers_owner = _auth(client, "imgowner@test.com")
        png_bytes = _make_png_bytes()
        upload_resp = client.post(
            "/api/notes/images",
            files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
            headers=headers_owner,
        )
        image_id = upload_resp.json()["id"]

        # Parent accesses
        mock_download.return_value = png_bytes
        headers_parent = _auth(client, "imgparent@test.com")
        resp = client.get(f"/api/notes/images/{image_id}", headers=headers_parent)
        assert resp.status_code == 200

    @patch("app.api.routes.notes.gcs_download_file")
    @patch("app.api.routes.notes.gcs_upload_file")
    def test_admin_can_access_any_image(self, mock_upload, mock_download, client, setup):
        mock_upload.return_value = "notes/1/abc.jpg"

        # Owner uploads
        headers_owner = _auth(client, "imgowner@test.com")
        png_bytes = _make_png_bytes()
        upload_resp = client.post(
            "/api/notes/images",
            files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
            headers=headers_owner,
        )
        image_id = upload_resp.json()["id"]

        # Admin accesses
        mock_download.return_value = png_bytes
        headers_admin = _auth(client, "imgadmin@test.com")
        resp = client.get(f"/api/notes/images/{image_id}", headers=headers_admin)
        assert resp.status_code == 200

    def test_nonexistent_image(self, client, setup):
        headers = _auth(client, "imgowner@test.com")
        resp = client.get("/api/notes/images/999999", headers=headers)
        assert resp.status_code == 404
