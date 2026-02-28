import pytest
from conftest import PASSWORD, _login, _auth


@pytest.fixture()
def users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher
    from app.models.course import Course

    parent = db_session.query(User).filter(User.email == "cc_parent@test.com").first()
    if parent:
        teacher = db_session.query(User).filter(User.email == "cc_teacher@test.com").first()
        other = db_session.query(User).filter(User.email == "cc_other@test.com").first()
        course = db_session.query(Course).filter(Course.name == "CC Test Course").first()
        return {"parent": parent, "teacher": teacher, "other": other, "course": course}

    hashed = get_password_hash(PASSWORD)
    parent = User(email="cc_parent@test.com", full_name="CC Parent", role=UserRole.PARENT, hashed_password=hashed)
    teacher = User(email="cc_teacher@test.com", full_name="CC Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    other = User(email="cc_other@test.com", full_name="CC Other", role=UserRole.TEACHER, hashed_password=hashed)
    db_session.add_all([parent, teacher, other])
    db_session.flush()

    teacher_rec = Teacher(user_id=teacher.id)
    db_session.add(teacher_rec)
    db_session.flush()

    course = Course(name="CC Test Course", teacher_id=teacher_rec.id, created_by_user_id=teacher.id)
    db_session.add(course)
    db_session.commit()

    for u in [parent, teacher, other]:
        db_session.refresh(u)
    db_session.refresh(course)
    return {"parent": parent, "teacher": teacher, "other": other, "course": course}


# ── CRUD ──────────────────────────────────────────────────────

class TestContentCRUD:
    def test_create_with_defaults(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id, "title": "Lecture 1",
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Lecture 1"
        assert data["content_type"] == "other"
        assert data["created_by_user_id"] == users["teacher"].id

    def test_create_all_fields(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id, "title": "Lab 1",
            "description": "First lab", "content_type": "labs",
            "reference_url": "https://example.com/lab",
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["description"] == "First lab"
        assert data["content_type"] == "labs"
        assert data["reference_url"] == "https://example.com/lab"

    def test_invalid_content_type_rejected(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id, "title": "Bad Type",
            "content_type": "invalid_type",
        }, headers=headers)
        assert resp.status_code == 422

    def test_nonexistent_course_rejected(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": 999999, "title": "No Course",
        }, headers=headers)
        assert resp.status_code == 404

    def test_list_by_course(self, client, users):
        headers = _auth(client, users["teacher"].email)
        # Create content first
        client.post("/api/course-contents/", json={
            "course_id": users["course"].id, "title": "List Item",
        }, headers=headers)

        resp = client.get(f"/api/course-contents/?course_id={users['course'].id}", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_filter_by_type(self, client, users):
        headers = _auth(client, users["teacher"].email)
        # Create with specific type
        client.post("/api/course-contents/", json={
            "course_id": users["course"].id, "title": "Notes Item", "content_type": "notes",
        }, headers=headers)

        resp = client.get(
            f"/api/course-contents/?course_id={users['course'].id}&content_type=notes",
            headers=headers,
        )
        assert resp.status_code == 200
        for item in resp.json():
            assert item["content_type"] == "notes"

    def test_get_single(self, client, users):
        headers = _auth(client, users["teacher"].email)
        create = client.post("/api/course-contents/", json={
            "course_id": users["course"].id, "title": "Single Item",
        }, headers=headers)
        cid = create.json()["id"]

        resp = client.get(f"/api/course-contents/{cid}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Single Item"



# ── Update ────────────────────────────────────────────────────

class TestContentUpdate:
    def _create_content(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id, "title": "Update Target",
        }, headers=headers)
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_creator_updates(self, client, users):
        cid = self._create_content(client, users)
        headers = _auth(client, users["teacher"].email)
        resp = client.patch(f"/api/course-contents/{cid}", json={
            "title": "Updated Title",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

    def test_non_creator_cannot_update(self, client, users):
        cid = self._create_content(client, users)
        headers = _auth(client, users["other"].email)
        resp = client.patch(f"/api/course-contents/{cid}", json={
            "title": "Hijacked",
        }, headers=headers)
        assert resp.status_code == 403

    def test_update_content_type(self, client, users):
        cid = self._create_content(client, users)
        headers = _auth(client, users["teacher"].email)
        resp = client.patch(f"/api/course-contents/{cid}", json={
            "content_type": "syllabus",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["content_type"] == "syllabus"



# ── Delete ────────────────────────────────────────────────────

class TestContentDelete:
    def _create_content(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id, "title": "Delete Target",
        }, headers=headers)
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_creator_deletes(self, client, users):
        cid = self._create_content(client, users)
        headers = _auth(client, users["teacher"].email)
        resp = client.delete(f"/api/course-contents/{cid}", headers=headers)
        assert resp.status_code == 204

    def test_non_creator_cannot_delete(self, client, users):
        cid = self._create_content(client, users)
        headers = _auth(client, users["other"].email)
        resp = client.delete(f"/api/course-contents/{cid}", headers=headers)
        assert resp.status_code == 403



# ── Permissions ───────────────────────────────────────────────

class TestContentPermissions:
    def test_unauthenticated_rejected(self, client):
        resp = client.post("/api/course-contents/", json={"course_id": 1, "title": "X"})
        assert resp.status_code == 401

    def test_any_user_can_create(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id, "title": "Parent Content",
        }, headers=headers)
        assert resp.status_code == 201

    def test_any_user_can_read(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get(
            f"/api/course-contents/?course_id={users['course'].id}",
            headers=headers,
        )
        assert resp.status_code == 200


# ── Download ─────────────────────────────────────────────────

class TestContentDownload:
    def _create_content_with_file(self, client, db_session, users):
        """Create a content item and attach a fake stored file."""
        from pathlib import Path
        from app.models.course_content import CourseContent
        from app.core.config import settings

        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id, "title": "File Content",
        }, headers=headers)
        assert resp.status_code == 201
        cid = resp.json()["id"]

        # Write a test file to the uploads dir
        upload_dir = Path(settings.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        test_file = upload_dir / "test_download.pdf"
        test_file.write_bytes(b"fake-pdf-content")

        # Set file metadata on the record
        cc = db_session.query(CourseContent).filter(CourseContent.id == cid).first()
        cc.file_path = "test_download.pdf"
        cc.original_filename = "lecture-notes.pdf"
        cc.file_size = 16
        cc.mime_type = "application/pdf"
        db_session.commit()

        return cid

    def test_download_file(self, client, db_session, users):
        cid = self._create_content_with_file(client, db_session, users)
        headers = _auth(client, users["teacher"].email)
        resp = client.get(f"/api/course-contents/{cid}/download", headers=headers)
        assert resp.status_code == 200
        assert resp.content == b"fake-pdf-content"
        assert "lecture-notes.pdf" in resp.headers.get("content-disposition", "")

    def test_download_no_file_returns_404(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id, "title": "No File Content",
        }, headers=headers)
        cid = resp.json()["id"]
        resp = client.get(f"/api/course-contents/{cid}/download", headers=headers)
        assert resp.status_code == 404

    def test_download_nonexistent_content_returns_404(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get("/api/course-contents/999999/download", headers=headers)
        assert resp.status_code == 404

    def test_download_unauthenticated_rejected(self, client):
        resp = client.get("/api/course-contents/1/download")
        assert resp.status_code == 401

    def test_response_includes_file_fields(self, client, db_session, users):
        cid = self._create_content_with_file(client, db_session, users)
        headers = _auth(client, users["teacher"].email)
        resp = client.get(f"/api/course-contents/{cid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_file"] is True
        assert data["original_filename"] == "lecture-notes.pdf"
        assert data["file_size"] == 16
        assert data["mime_type"] == "application/pdf"

    def test_content_without_file_has_file_false(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": users["course"].id, "title": "No File",
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["has_file"] is False
        assert data["original_filename"] is None


# ── File Upload (no AI) ──────────────────────────────────────

class TestContentFileUpload:
    def test_upload_file_creates_content_with_file(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post(
            "/api/course-contents/upload",
            data={"course_id": str(users["course"].id), "title": "My Notes"},
            files={"file": ("notes.txt", b"Hello world notes content", "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["has_file"] is True
        assert data["original_filename"] == "notes.txt"
        assert data["file_size"] == len(b"Hello world notes content")
        assert data["mime_type"] == "text/plain"
        assert data["title"] == "My Notes"
        assert data["text_content"]  # extracted text should be populated

    def test_upload_file_uses_filename_as_title_fallback(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post(
            "/api/course-contents/upload",
            data={"course_id": str(users["course"].id)},
            files={"file": ("chapter5.txt", b"Chapter 5 content", "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "chapter5.txt"

    def test_upload_file_downloadable(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post(
            "/api/course-contents/upload",
            data={"course_id": str(users["course"].id), "title": "Download Test"},
            files={"file": ("test.txt", b"download me", "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 201
        cid = resp.json()["id"]

        # Now download it
        dl_resp = client.get(f"/api/course-contents/{cid}/download", headers=headers)
        assert dl_resp.status_code == 200
        assert dl_resp.content == b"download me"

    def test_upload_unauthenticated_rejected(self, client, users):
        resp = client.post(
            "/api/course-contents/upload",
            data={"course_id": str(users["course"].id)},
            files={"file": ("x.txt", b"data", "text/plain")},
        )
        assert resp.status_code == 401

    def test_upload_invalid_course_returns_404(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post(
            "/api/course-contents/upload",
            data={"course_id": "99999"},
            files={"file": ("x.txt", b"data", "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 404


# ── Parameterized 404 tests ──────────────────────────────────


@pytest.mark.parametrize("method,url,json_body", [
    ("GET", "/api/course-contents/999999", None),
    ("PATCH", "/api/course-contents/999999", {"title": "X"}),
    ("DELETE", "/api/course-contents/999999", None),
])
def test_nonexistent_content_returns_404(client, users, method, url, json_body):
    headers = _auth(client, users["teacher"].email)
    kwargs = {"headers": headers}
    if json_body:
        kwargs["json"] = json_body
    resp = getattr(client, method.lower())(url, **kwargs)
    assert resp.status_code == 404


# ── Parent access to child-created content (#896) ────────────

class TestParentAccessChildContent:
    """Regression test: parent must be able to access content in a course
    created by their child, even if the child is not enrolled in it."""

    @pytest.fixture()
    def family(self, db_session):
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.models.student import Student, parent_students
        from app.models.course import Course

        # Re-use existing rows if already created by a prior test
        parent = db_session.query(User).filter(User.email == "family_parent@test.com").first()
        if parent:
            child = db_session.query(User).filter(User.email == "family_child@test.com").first()
            child_course = db_session.query(Course).filter(
                Course.created_by_user_id == child.id, Course.is_default == True,
            ).first()
            return {"parent": parent, "child": child, "child_course": child_course}

        hashed = get_password_hash(PASSWORD)

        parent = User(email="family_parent@test.com", full_name="Family Parent", role=UserRole.PARENT, hashed_password=hashed)
        child = User(email="family_child@test.com", full_name="Family Child", role=UserRole.STUDENT, hashed_password=hashed)
        db_session.add_all([parent, child])
        db_session.flush()

        student = Student(user_id=child.id)
        db_session.add(student)
        db_session.flush()

        # Link parent to child
        db_session.execute(parent_students.insert().values(
            parent_id=parent.id, student_id=student.id, relationship_type="parent",
        ))

        # Child's default course (private, not enrolled — just created)
        child_course = Course(
            name="Child Main Course", created_by_user_id=child.id,
            is_private=True, is_default=True,
        )
        db_session.add(child_course)
        db_session.commit()

        for u in [parent, child]:
            db_session.refresh(u)
        db_session.refresh(child_course)
        return {"parent": parent, "child": child, "child_course": child_course}

    def test_parent_can_read_child_created_content(self, client, family):
        """Parent should access content in a course their child created (#896)."""
        child_headers = _auth(client, family["child"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": family["child_course"].id,
            "title": "Child Notes",
            "content_type": "notes",
        }, headers=child_headers)
        assert resp.status_code == 201
        content_id = resp.json()["id"]

        # Parent reads the same content
        parent_headers = _auth(client, family["parent"].email)
        resp = client.get(f"/api/course-contents/{content_id}", headers=parent_headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Child Notes"

    def test_parent_sees_child_content_in_list(self, client, family):
        """Parent list endpoint should include child-created course content."""
        child_headers = _auth(client, family["child"].email)
        client.post("/api/course-contents/", json={
            "course_id": family["child_course"].id,
            "title": "Child List Item",
            "content_type": "notes",
        }, headers=child_headers)

        parent_headers = _auth(client, family["parent"].email)
        resp = client.get("/api/course-contents/", headers=parent_headers)
        assert resp.status_code == 200
        titles = [item["title"] for item in resp.json()]
        assert "Child List Item" in titles

    def test_parent_can_edit_child_created_content(self, client, family):
        """Parent should be able to edit content created by their child (#930)."""
        child_headers = _auth(client, family["child"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": family["child_course"].id,
            "title": "Child Editable",
            "text_content": "Original text",
            "content_type": "notes",
        }, headers=child_headers)
        assert resp.status_code == 201
        content_id = resp.json()["id"]

        parent_headers = _auth(client, family["parent"].email)
        resp = client.patch(f"/api/course-contents/{content_id}", json={
            "text_content": "Parent edited text",
        }, headers=parent_headers)
        assert resp.status_code == 200
        assert resp.json()["text_content"] == "Parent edited text"

    def test_parent_can_delete_child_created_content(self, client, family):
        """Parent should be able to archive content created by their child (#930)."""
        child_headers = _auth(client, family["child"].email)
        resp = client.post("/api/course-contents/", json={
            "course_id": family["child_course"].id,
            "title": "Child Deletable",
            "content_type": "notes",
        }, headers=child_headers)
        assert resp.status_code == 201
        content_id = resp.json()["id"]

        parent_headers = _auth(client, family["parent"].email)
        resp = client.delete(f"/api/course-contents/{content_id}", headers=parent_headers)
        assert resp.status_code == 204
