import pytest

PASSWORD = "password123!"


def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}


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

    def test_get_nonexistent_returns_404(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get("/api/course-contents/999999", headers=headers)
        assert resp.status_code == 404


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

    def test_update_nonexistent_returns_404(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.patch("/api/course-contents/999999", json={"title": "X"}, headers=headers)
        assert resp.status_code == 404


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

    def test_delete_nonexistent_returns_404(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.delete("/api/course-contents/999999", headers=headers)
        assert resp.status_code == 404


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
