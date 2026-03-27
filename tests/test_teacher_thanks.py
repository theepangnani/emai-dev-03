"""Tests for Teacher Thanks (Gratitude) API routes (#2226)."""
import pytest

from conftest import PASSWORD, _auth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def thanks_users(db_session):
    """Create users needed for teacher-thanks tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.teacher import Teacher

    hashed = get_password_hash(PASSWORD)

    parent = db_session.query(User).filter(User.email == "thanksparent@test.com").first()
    if parent:
        student = db_session.query(User).filter(User.email == "thanksstudent@test.com").first()
        teacher_user = db_session.query(User).filter(User.email == "thanksteacher@test.com").first()
        teacher = db_session.query(Teacher).filter(Teacher.user_id == teacher_user.id).first()
        return {"parent": parent, "student": student, "teacher_user": teacher_user, "teacher": teacher}

    parent = User(email="thanksparent@test.com", full_name="Thanks Parent", role=UserRole.PARENT, hashed_password=hashed)
    student = User(email="thanksstudent@test.com", full_name="Thanks Student", role=UserRole.STUDENT, hashed_password=hashed)
    teacher_user = User(email="thanksteacher@test.com", full_name="Thanks Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    db_session.add_all([parent, student, teacher_user])
    db_session.commit()

    teacher = Teacher(user_id=teacher_user.id, department="Math")
    db_session.add(teacher)
    db_session.commit()

    return {"parent": parent, "student": student, "teacher_user": teacher_user, "teacher": teacher}


# ---------------------------------------------------------------------------
# POST /api/teachers/{teacher_id}/thank
# ---------------------------------------------------------------------------

def test_send_thanks_as_student(client, thanks_users):
    headers = _auth(client, "thanksstudent@test.com")
    teacher_id = thanks_users["teacher"].id
    resp = client.post(f"/api/teachers/{teacher_id}/thank", json={"message": "Great class!"}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["teacher_id"] == teacher_id
    assert data["message"] == "Great class!"


def test_send_thanks_as_parent(client, thanks_users):
    headers = _auth(client, "thanksparent@test.com")
    teacher_id = thanks_users["teacher"].id
    resp = client.post(f"/api/teachers/{teacher_id}/thank", json={}, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["teacher_id"] == teacher_id


def test_send_thanks_duplicate_same_day(client, thanks_users):
    headers = _auth(client, "thanksstudent@test.com")
    teacher_id = thanks_users["teacher"].id
    # First one may succeed or already exist from earlier test
    client.post(f"/api/teachers/{teacher_id}/thank", json={}, headers=headers)
    # Second one same day should be 429
    resp = client.post(f"/api/teachers/{teacher_id}/thank", json={}, headers=headers)
    assert resp.status_code == 429


def test_send_thanks_teacher_not_found(client, thanks_users):
    headers = _auth(client, "thanksstudent@test.com")
    resp = client.post("/api/teachers/99999/thank", json={}, headers=headers)
    assert resp.status_code == 404


def test_send_thanks_unauthenticated(client):
    resp = client.post("/api/teachers/1/thank", json={})
    assert resp.status_code == 401


def test_send_thanks_teacher_role_forbidden(client, thanks_users):
    headers = _auth(client, "thanksteacher@test.com")
    teacher_id = thanks_users["teacher"].id
    resp = client.post(f"/api/teachers/{teacher_id}/thank", json={}, headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/teachers/{teacher_id}/thanks-count
# ---------------------------------------------------------------------------

def test_get_thanks_count(client, thanks_users):
    headers = _auth(client, "thanksstudent@test.com")
    teacher_id = thanks_users["teacher"].id
    resp = client.get(f"/api/teachers/{teacher_id}/thanks-count", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_count" in data
    assert "week_count" in data
    assert data["teacher_id"] == teacher_id


def test_get_thanks_count_not_found(client, thanks_users):
    headers = _auth(client, "thanksstudent@test.com")
    resp = client.get("/api/teachers/99999/thanks-count", headers=headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/teachers/{teacher_id}/thanks-status
# ---------------------------------------------------------------------------

def test_get_thanks_status(client, thanks_users):
    headers = _auth(client, "thanksstudent@test.com")
    teacher_id = thanks_users["teacher"].id
    resp = client.get(f"/api/teachers/{teacher_id}/thanks-status", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "thanked_today" in data


# ---------------------------------------------------------------------------
# GET /api/teachers/me/thanks-count  (route ordering: must not 422)
# ---------------------------------------------------------------------------

def test_get_my_thanks_count_as_teacher(client, thanks_users):
    headers = _auth(client, "thanksteacher@test.com")
    resp = client.get("/api/teachers/me/thanks-count", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_count" in data
    assert "week_count" in data


def test_get_my_thanks_count_non_teacher_forbidden(client, thanks_users):
    headers = _auth(client, "thanksstudent@test.com")
    resp = client.get("/api/teachers/me/thanks-count", headers=headers)
    assert resp.status_code == 403
