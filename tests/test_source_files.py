"""Tests for source files feature (#1005).

Covers: multi-file upload, source files listing, source file download,
permanent delete cascade, and access control.
"""
import pytest
from unittest.mock import patch, MagicMock
from conftest import PASSWORD, _auth

_FILE_STORE: dict = {}  # in-memory fake GCS store keyed by gcs_path


def _fake_upload(gcs_path, data, content_type):
    _FILE_STORE[gcs_path] = data


def _fake_download(gcs_path):
    return _FILE_STORE.get(gcs_path, b"")


def _fake_delete(gcs_path):
    _FILE_STORE.pop(gcs_path, None)


@pytest.fixture(autouse=True)
def mock_gcs(monkeypatch):
    """Enable GCS path and stub out actual GCS calls for all tests in this module."""
    _FILE_STORE.clear()
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_gcs", True)
    with patch("app.api.routes.course_contents.gcs_service") as mock:
        mock.upload_file.side_effect = _fake_upload
        mock.download_file.side_effect = _fake_download
        mock.delete_file.side_effect = _fake_delete
        yield mock


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


class TestMultiFileUpload:
    """Tests for POST /api/course-contents/upload-multi."""

    def test_upload_multi_files(self, client, users):
        headers = _auth(client, users["teacher"].email)
        files = [
            ("files", ("file1.txt", b"Content of file 1", "text/plain")),
            ("files", ("file2.txt", b"Content of file 2", "text/plain")),
        ]
        resp = client.post(
            "/api/course-contents/upload-multi",
            files=files,
            data={"course_id": str(users["course"].id), "title": "Multi-file upload"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Multi-file upload"
        # With hierarchy (#1740 / §6.98 Rule 3), master gets first file's text
        assert data["material_group_id"] is not None
        assert "Content of file 1" in (data.get("text_content") or "")

    def test_upload_multi_uses_filenames_as_default_title(self, client, users):
        headers = _auth(client, users["teacher"].email)
        files = [
            ("files", ("notes.txt", b"Some notes", "text/plain")),
            ("files", ("summary.txt", b"A summary", "text/plain")),
        ]
        resp = client.post(
            "/api/course-contents/upload-multi",
            files=files,
            data={"course_id": str(users["course"].id)},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        # Master title uses first filename without extension
        assert data["title"] == "notes"

    def test_upload_multi_no_files_rejected(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post(
            "/api/course-contents/upload-multi",
            data={"course_id": str(users["course"].id)},
            headers=headers,
        )
        assert resp.status_code == 422  # FastAPI validation error for missing files

    def test_upload_multi_bad_course_rejected(self, client, users):
        headers = _auth(client, users["teacher"].email)
        files = [("files", ("f.txt", b"data", "text/plain"))]
        resp = client.post(
            "/api/course-contents/upload-multi",
            files=files,
            data={"course_id": "999999"},
            headers=headers,
        )
        assert resp.status_code == 404


class TestSourceFilesListing:
    """Tests for GET /api/course-contents/{id}/source-files."""

    def _create_content_with_sources(self, client, users):
        headers = _auth(client, users["teacher"].email)
        files = [
            ("files", ("doc1.txt", b"Hello world", "text/plain")),
            ("files", ("doc2.txt", b"Goodbye world", "text/plain")),
            ("files", ("image.txt", b"An image description", "text/plain")),
        ]
        resp = client.post(
            "/api/course-contents/upload-multi",
            files=files,
            data={"course_id": str(users["course"].id), "title": "With Sources"},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()

    def test_list_source_files(self, client, users, db_session):
        """With §6.98 Rule 3, master is first file; remaining files are subs."""
        from app.models.course_content import CourseContent
        content = self._create_content_with_sources(client, users)
        headers = _auth(client, users["teacher"].email)
        resp = client.get(f"/api/course-contents/{content['id']}/source-files", headers=headers)
        assert resp.status_code == 200
        # First file is master; remaining 2 files are sub-materials
        subs = db_session.query(CourseContent).filter(
            CourseContent.parent_content_id == content['id'],
        ).all()
        assert len(subs) == 2  # First file is master; remaining 2 are subs

    def test_list_source_files_returns_metadata(self, client, users):
        content = self._create_content_with_sources(client, users)
        headers = _auth(client, users["teacher"].email)
        resp = client.get(f"/api/course-contents/{content['id']}/source-files", headers=headers)
        data = resp.json()
        for f in data:
            assert "id" in f
            assert "filename" in f
            assert "file_type" in f
            assert "file_size" in f
            assert "created_at" in f
            # Binary data should NOT be in the response
            assert "file_data" not in f

    def test_list_source_files_not_found(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get("/api/course-contents/999999/source-files", headers=headers)
        assert resp.status_code == 404

    def test_list_source_files_empty_for_single_upload(self, client, users):
        """Content created via regular upload has no source files."""
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id,
            "title": "No Sources",
            "text_content": "Just text",
        }, headers=headers)
        assert resp.status_code == 201
        content_id = resp.json()["id"]

        resp = client.get(f"/api/course-contents/{content_id}/source-files", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestSourceFileDownload:
    """Tests for GET /api/course-contents/{id}/source-files/{file_id}/download."""

    def test_download_source_file(self, client, users):
        headers = _auth(client, users["teacher"].email)
        # Upload multi files
        file_content = b"Test file content for download"
        files = [("files", ("download_me.txt", file_content, "text/plain"))]
        resp = client.post(
            "/api/course-contents/upload-multi",
            files=files,
            data={"course_id": str(users["course"].id), "title": "Download Test"},
            headers=headers,
        )
        assert resp.status_code == 201
        content_id = resp.json()["id"]

        # List source files
        resp = client.get(f"/api/course-contents/{content_id}/source-files", headers=headers)
        assert resp.status_code == 200
        file_id = resp.json()[0]["id"]

        # Download
        resp = client.get(f"/api/course-contents/{content_id}/source-files/{file_id}/download", headers=headers)
        assert resp.status_code == 200
        assert resp.content == file_content
        assert "download_me.txt" in resp.headers.get("content-disposition", "")

    def test_download_nonexistent_file(self, client, users):
        headers = _auth(client, users["teacher"].email)
        # Create content first
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id,
            "title": "No Files",
        }, headers=headers)
        content_id = resp.json()["id"]

        resp = client.get(f"/api/course-contents/{content_id}/source-files/999999/download", headers=headers)
        assert resp.status_code == 404


class TestSourceFilesCount:
    """Tests that source_files_count appears in CourseContent responses."""

    def test_create_response_includes_count(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id,
            "title": "Count Test",
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["source_files_count"] == 0

    def test_multi_upload_response_includes_count(self, client, users):
        """With §6.98 Rule 3, master IS the first file so has 1 source file.
        Master now aggregates sub-material source files too (#1841)."""
        headers = _auth(client, users["teacher"].email)
        files = [
            ("files", ("a.txt", b"AAA", "text/plain")),
            ("files", ("b.txt", b"BBB", "text/plain")),
        ]
        resp = client.post(
            "/api/course-contents/upload-multi",
            files=files,
            data={"course_id": str(users["course"].id), "title": "Multi Count"},
            headers=headers,
        )
        assert resp.status_code == 201
        # Master has 1 own file + 1 sub-material file = 2 (#1841)
        assert resp.json()["source_files_count"] == 2
        assert resp.json()["material_group_id"] is not None

    def test_get_response_includes_count(self, client, users):
        headers = _auth(client, users["teacher"].email)
        files = [
            ("files", ("x.txt", b"XXX", "text/plain")),
        ]
        resp = client.post(
            "/api/course-contents/upload-multi",
            files=files,
            data={"course_id": str(users["course"].id), "title": "Get Count"},
            headers=headers,
        )
        content_id = resp.json()["id"]

        resp = client.get(f"/api/course-contents/{content_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["source_files_count"] == 1

    def test_list_response_includes_count(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get(f"/api/course-contents/?course_id={users['course'].id}", headers=headers)
        assert resp.status_code == 200
        for item in resp.json():
            assert "source_files_count" in item


class TestSourceFilesCascadeDelete:
    """Tests that source files are cleaned up on permanent delete."""

    def test_permanent_delete_removes_source_files(self, client, users, db_session):
        """With hierarchy (#1740), deleting master also removes sub-materials and their source files."""
        from app.models.course_content import CourseContent

        headers = _auth(client, users["teacher"].email)
        files = [
            ("files", ("del1.txt", b"Delete me 1", "text/plain")),
            ("files", ("del2.txt", b"Delete me 2", "text/plain")),
        ]
        resp = client.post(
            "/api/course-contents/upload-multi",
            files=files,
            data={"course_id": str(users["course"].id), "title": "Delete Test"},
            headers=headers,
        )
        master_id = resp.json()["id"]
        group_id = resp.json()["material_group_id"]

        # Verify sub-materials exist (2 files => master + 1 sub per §6.98 Rule 3)
        subs = db_session.query(CourseContent).filter(
            CourseContent.parent_content_id == master_id,
        ).all()
        assert len(subs) == 1

        # Archive master first (required before permanent delete)
        client.delete(f"/api/course-contents/{master_id}", headers=headers)

        # Permanent delete master
        resp = client.delete(f"/api/course-contents/{master_id}/permanent", headers=headers)
        assert resp.status_code == 204

        # Master should be gone
        db_session.expire_all()
        master = db_session.query(CourseContent).filter(CourseContent.id == master_id).first()
        assert master is None
