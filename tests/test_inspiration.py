import pytest

PASSWORD = "Password123!"


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

    admin = db_session.query(User).filter(User.email == "insp_admin@test.com").first()
    if admin:
        parent = db_session.query(User).filter(User.email == "insp_parent@test.com").first()
        teacher = db_session.query(User).filter(User.email == "insp_teacher@test.com").first()
        student = db_session.query(User).filter(User.email == "insp_student@test.com").first()
        return {"admin": admin, "parent": parent, "teacher": teacher, "student": student}

    hashed = get_password_hash(PASSWORD)
    admin = User(email="insp_admin@test.com", full_name="Insp Admin", role=UserRole.ADMIN, hashed_password=hashed)
    parent = User(email="insp_parent@test.com", full_name="Insp Parent", role=UserRole.PARENT, hashed_password=hashed)
    teacher = User(email="insp_teacher@test.com", full_name="Insp Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    student = User(email="insp_student@test.com", full_name="Insp Student", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add_all([admin, parent, teacher, student])
    db_session.commit()

    for u in [admin, parent, teacher, student]:
        db_session.refresh(u)

    return {"admin": admin, "parent": parent, "teacher": teacher, "student": student}


@pytest.fixture()
def seed_messages(db_session):
    """Seed some test messages into the DB."""
    from app.models.inspiration_message import InspirationMessage

    msgs = [
        InspirationMessage(role="parent", text="Parent msg 1", author="Author A", is_active=True),
        InspirationMessage(role="parent", text="Parent msg 2", author=None, is_active=True),
        InspirationMessage(role="teacher", text="Teacher msg 1", author="Author B", is_active=True),
        InspirationMessage(role="student", text="Student msg 1", author=None, is_active=True),
        InspirationMessage(role="parent", text="Inactive parent msg", author=None, is_active=False),
    ]
    db_session.add_all(msgs)
    db_session.commit()
    for m in msgs:
        db_session.refresh(m)
    return msgs


# ── GET /api/inspiration/random ─────────────────────────────


class TestRandomMessage:
    def test_parent_gets_parent_message(self, client, users, seed_messages):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/inspiration/random", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "parent"
        assert "Parent msg" in data["text"]

    def test_teacher_gets_teacher_message(self, client, users, seed_messages):
        headers = _auth(client, users["teacher"].email)
        resp = client.get("/api/inspiration/random", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "teacher"

    def test_student_gets_student_message(self, client, users, seed_messages):
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/inspiration/random", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "student"

    def test_inactive_not_returned(self, client, users, seed_messages):
        """Parent should never get the inactive message."""
        headers = _auth(client, users["parent"].email)
        for _ in range(20):
            resp = client.get("/api/inspiration/random", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "Inactive" not in data["text"]


# ── Admin CRUD ───────────────────────────────────────────────


class TestAdminCRUD:
    def test_list_messages(self, client, users, seed_messages):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/inspiration/messages", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 5

    def test_list_filter_by_role(self, client, users, seed_messages):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/inspiration/messages?role=teacher", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert all(m["role"] == "teacher" for m in data)

    def test_create_message(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.post("/api/inspiration/messages", json={
            "role": "student",
            "text": "New test message",
            "author": "Test Author",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["text"] == "New test message"
        assert data["author"] == "Test Author"
        assert data["role"] == "student"
        assert data["is_active"] is True

    def test_create_invalid_role_rejected(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.post("/api/inspiration/messages", json={
            "role": "invalid",
            "text": "Bad role message",
        }, headers=headers)
        assert resp.status_code == 400

    def test_update_message(self, client, users, seed_messages):
        headers = _auth(client, users["admin"].email)
        msg_id = seed_messages[0].id
        resp = client.patch(f"/api/inspiration/messages/{msg_id}", json={
            "text": "Updated message text",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["text"] == "Updated message text"

    def test_toggle_active(self, client, users, seed_messages):
        headers = _auth(client, users["admin"].email)
        msg_id = seed_messages[0].id
        resp = client.patch(f"/api/inspiration/messages/{msg_id}", json={
            "is_active": False,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_delete_message(self, client, users, seed_messages):
        headers = _auth(client, users["admin"].email)
        msg_id = seed_messages[3].id  # student msg
        resp = client.delete(f"/api/inspiration/messages/{msg_id}", headers=headers)
        assert resp.status_code == 200

    def test_delete_nonexistent_returns_404(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.delete("/api/inspiration/messages/999999", headers=headers)
        assert resp.status_code == 404

    def test_non_admin_cannot_list(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/inspiration/messages", headers=headers)
        assert resp.status_code == 403

    def test_non_admin_cannot_create(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/inspiration/messages", json={
            "role": "teacher",
            "text": "Unauthorized create",
        }, headers=headers)
        assert resp.status_code == 403


# ── Seed endpoint ────────────────────────────────────────────


class TestSeedEndpoint:
    def test_seed_requires_admin(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/inspiration/seed", headers=headers)
        assert resp.status_code == 403

    def test_seed_skips_if_not_empty(self, client, users, seed_messages):
        headers = _auth(client, users["admin"].email)
        resp = client.post("/api/inspiration/seed", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["seeded"] == 0
