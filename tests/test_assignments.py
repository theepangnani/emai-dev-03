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

    parent = db_session.query(User).filter(User.email == "asgn_parent@test.com").first()
    if parent:
        teacher = db_session.query(User).filter(User.email == "asgn_teacher@test.com").first()
        teacher_rec = db_session.query(Teacher).filter(Teacher.user_id == teacher.id).first()
        course = db_session.query(Course).filter(Course.name == "Asgn Test Course").first()
        return {"parent": parent, "teacher": teacher, "teacher_rec": teacher_rec, "course": course}

    hashed = get_password_hash(PASSWORD)
    parent = User(email="asgn_parent@test.com", full_name="Asgn Parent", role=UserRole.PARENT, hashed_password=hashed)
    teacher = User(email="asgn_teacher@test.com", full_name="Asgn Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    db_session.add_all([parent, teacher])
    db_session.flush()

    teacher_rec = Teacher(user_id=teacher.id)
    db_session.add(teacher_rec)
    db_session.flush()

    course = Course(name="Asgn Test Course", teacher_id=teacher_rec.id, created_by_user_id=teacher.id)
    db_session.add(course)
    db_session.commit()

    for u in [parent, teacher]:
        db_session.refresh(u)
    db_session.refresh(teacher_rec)
    db_session.refresh(course)
    return {"parent": parent, "teacher": teacher, "teacher_rec": teacher_rec, "course": course}


class TestAssignmentCRUD:
    def test_create_assignment(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/assignments/", json={
            "title": "Homework 1", "course_id": users["course"].id,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Homework 1"
        assert data["course_id"] == users["course"].id

    def test_create_with_all_fields(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/assignments/", json={
            "title": "Full HW", "description": "All fields",
            "course_id": users["course"].id,
            "due_date": "2026-06-01T23:59:00", "max_points": 100.0,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "All fields"
        assert data["max_points"] == 100.0

    def test_list_assignments(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/assignments/", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_by_course_id(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get(f"/api/assignments/?course_id={users['course'].id}", headers=headers)
        assert resp.status_code == 200
        for a in resp.json():
            assert a["course_id"] == users["course"].id

    def test_get_by_id(self, client, users):
        headers = _auth(client, users["teacher"].email)
        # Create one first
        create = client.post("/api/assignments/", json={
            "title": "Get Test", "course_id": users["course"].id,
        }, headers=headers)
        aid = create.json()["id"]

        resp = client.get(f"/api/assignments/{aid}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Get Test"

    def test_nonexistent_returns_404(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get("/api/assignments/999999", headers=headers)
        assert resp.status_code == 404


class TestAssignmentPermissions:
    def test_unauthenticated_rejected(self, client):
        resp = client.post("/api/assignments/", json={"title": "X", "course_id": 1})
        assert resp.status_code == 401

    def test_any_role_can_create(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/assignments/", json={
            "title": "Parent Created", "course_id": users["course"].id,
        }, headers=headers)
        assert resp.status_code == 200

    def test_any_role_can_list(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/assignments/", headers=headers)
        assert resp.status_code == 200
