"""Tests for the Source Files feature (#1005).

Tests the SourceFile model, API endpoints for listing/uploading/downloading
source files attached to CourseContent items.
"""

import pytest
from conftest import PASSWORD, _auth


@pytest.fixture()
def users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher
    from app.models.course import Course

    parent = db_session.query(User).filter(User.email == "sf_parent@test.com").first()
    if parent:
        teacher = db_session.query(User).filter(User.email == "sf_teacher@test.com").first()
        other = db_session.query(User).filter(User.email == "sf_other@test.com").first()
        course = db_session.query(Course).filter(Course.name == "SF Test Course").first()
        return {"parent": parent, "teacher": teacher, "other": other, "course": course}

    hashed = get_password_hash(PASSWORD)
    parent = User(email="sf_parent@test.com", full_name="SF Parent", role=UserRole.PARENT, hashed_password=hashed)
    teacher = User(email="sf_teacher@test.com", full_name="SF Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    other = User(email="sf_other@test.com", full_name="SF Other", role=UserRole.TEACHER, hashed_password=hashed)
    db_session.add_all([parent, teacher, other])
    db_session.flush()

    teacher_rec = Teacher(user_id=teacher.id)
    db_session.add(teacher_rec)
    db_session.flush()

    course = Course(name="SF Test Course", teacher_id=teacher_rec.id, created_by_user_id=teacher.id)
    db_session.add(course)
    db_session.commit()

    for u in [parent, teacher, other]:
        db_session.refresh(u)
    db_session.refresh(course)
    return {"parent": parent, "teacher": teacher, "other": other, "course": course}


@pytest.fixture()
def content_with_source_files(client, users, db_session):
    """Create a CourseContent and attach source files."""
    headers = _auth(client, users["teacher"].email)

    # Create content
    resp = client.post("/api/course-contents/", json={
        "course_id": users["course"].id,
        "title": "Multi-file Material",
        "text_content": "Combined text from files",
    }, headers=headers)
    assert resp.status_code == 201
    content = resp.json()

    # Attach source files
    files = [
        ("files", ("notes.txt", b"Hello world content", "text/plain")),
        ("files", ("image.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")),
    ]
    resp = client.post(
        f"/api/course-contents/{content['id']}/source-files",
        files=files,
        headers=headers,
    )
    assert resp.status_code == 201

    return content


# ── List source files ────────────────────────────────────────

class TestListSourceFiles:
    def test_list_source_files(self, client, users, content_with_source_files):
        headers = _auth(client, users["teacher"].email)
        content_id = content_with_source_files["id"]

        resp = client.get(f"/api/course-contents/{content_id}/source-files", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        filenames = {f["filename"] for f in data}
        assert "notes.txt" in filenames
        assert "image.png" in filenames

    def test_list_empty_when_no_files(self, client, users):
        headers = _auth(client, users["teacher"].email)

        # Create content without source files
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id,
            "title": "No Source Files",
        }, headers=headers)
        assert resp.status_code == 201
        content_id = resp.json()["id"]

        resp = client.get(f"/api/course-contents/{content_id}/source-files", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_requires_auth(self, client, content_with_source_files):
        content_id = content_with_source_files["id"]
        resp = client.get(f"/api/course-contents/{content_id}/source-files")
        assert resp.status_code == 401

    def test_list_not_found(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get("/api/course-contents/99999/source-files", headers=headers)
        assert resp.status_code == 404


# ── Attach source files ─────────────────────────────────────

class TestAttachSourceFiles:
    def test_attach_single_file(self, client, users):
        headers = _auth(client, users["teacher"].email)

        # Create content
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id,
            "title": "Attach Test",
        }, headers=headers)
        content_id = resp.json()["id"]

        files = [("files", ("doc.pdf", b"%PDF-1.4 content here", "application/pdf"))]
        resp = client.post(
            f"/api/course-contents/{content_id}/source-files",
            files=files,
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert len(data) == 1
        assert data[0]["filename"] == "doc.pdf"
        assert data[0]["file_type"] == "application/pdf"
        assert data[0]["file_size"] > 0

    def test_attach_multiple_files(self, client, users):
        headers = _auth(client, users["teacher"].email)

        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id,
            "title": "Multi-attach Test",
        }, headers=headers)
        content_id = resp.json()["id"]

        files = [
            ("files", ("a.txt", b"aaa", "text/plain")),
            ("files", ("b.txt", b"bbb", "text/plain")),
            ("files", ("c.txt", b"ccc", "text/plain")),
        ]
        resp = client.post(
            f"/api/course-contents/{content_id}/source-files",
            files=files,
            headers=headers,
        )
        assert resp.status_code == 201
        assert len(resp.json()) == 3

    def test_attach_not_found(self, client, users):
        headers = _auth(client, users["teacher"].email)
        files = [("files", ("test.txt", b"test", "text/plain"))]
        resp = client.post(
            "/api/course-contents/99999/source-files",
            files=files,
            headers=headers,
        )
        assert resp.status_code == 404


# ── Download source file ────────────────────────────────────

class TestDownloadSourceFile:
    def test_download_text_file(self, client, users, content_with_source_files):
        headers = _auth(client, users["teacher"].email)
        content_id = content_with_source_files["id"]

        # Get file list to find the text file
        resp = client.get(f"/api/course-contents/{content_id}/source-files", headers=headers)
        files = resp.json()
        text_file = next(f for f in files if f["filename"] == "notes.txt")

        resp = client.get(f"/api/source-files/{text_file['id']}/download", headers=headers)
        assert resp.status_code == 200
        assert b"Hello world content" in resp.content
        assert "text/plain" in resp.headers.get("content-type", "")
        assert 'filename="notes.txt"' in resp.headers.get("content-disposition", "")

    def test_download_image_inline(self, client, users, content_with_source_files):
        headers = _auth(client, users["teacher"].email)
        content_id = content_with_source_files["id"]

        resp = client.get(f"/api/course-contents/{content_id}/source-files", headers=headers)
        files = resp.json()
        img_file = next(f for f in files if f["filename"] == "image.png")

        resp = client.get(f"/api/source-files/{img_file['id']}/download", headers=headers)
        assert resp.status_code == 200
        assert "image/png" in resp.headers.get("content-type", "")
        # Should be inline for images
        assert "inline" in resp.headers.get("content-disposition", "")

    def test_download_not_found(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get("/api/source-files/99999/download", headers=headers)
        assert resp.status_code == 404

    def test_download_requires_auth(self, client, content_with_source_files):
        headers_none: dict = {}
        resp = client.get(f"/api/source-files/1/download", headers=headers_none)
        assert resp.status_code == 401


# ── Source files count in content response ───────────────────

class TestSourceFilesCount:
    def test_content_get_includes_count(self, client, users, content_with_source_files):
        headers = _auth(client, users["teacher"].email)
        content_id = content_with_source_files["id"]

        resp = client.get(f"/api/course-contents/{content_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["source_files_count"] == 2

    def test_content_get_zero_when_none(self, client, users):
        headers = _auth(client, users["teacher"].email)

        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id,
            "title": "No Source Files Count Test",
        }, headers=headers)
        content_id = resp.json()["id"]

        resp = client.get(f"/api/course-contents/{content_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["source_files_count"] == 0


# ── Source files metadata ────────────────────────────────────

class TestSourceFileMetadata:
    def test_file_metadata_correct(self, client, users, content_with_source_files):
        headers = _auth(client, users["teacher"].email)
        content_id = content_with_source_files["id"]

        resp = client.get(f"/api/course-contents/{content_id}/source-files", headers=headers)
        files = resp.json()
        text_file = next(f for f in files if f["filename"] == "notes.txt")

        assert text_file["file_type"] == "text/plain"
        assert text_file["file_size"] == len(b"Hello world content")
        assert text_file["course_content_id"] == content_id
        assert "created_at" in text_file
