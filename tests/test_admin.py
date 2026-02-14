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

    admin_email = "adm_admin@test.com"
    admin = db_session.query(User).filter(User.email == admin_email).first()
    if admin:
        parent = db_session.query(User).filter(User.email == "adm_parent@test.com").first()
        student = db_session.query(User).filter(User.email == "adm_student@test.com").first()
        return {"admin": admin, "parent": parent, "student": student}

    hashed = get_password_hash(PASSWORD)
    admin = User(email=admin_email, full_name="Admin Boss", role=UserRole.ADMIN, hashed_password=hashed)
    parent = User(email="adm_parent@test.com", full_name="Admin Parent", role=UserRole.PARENT, hashed_password=hashed)
    student = User(email="adm_student@test.com", full_name="Admin Student", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add_all([admin, parent, student])
    db_session.commit()
    for u in [admin, parent, student]:
        db_session.refresh(u)
    return {"admin": admin, "parent": parent, "student": student}


# ── Original test ─────────────────────────────────────────────

def test_admin_stats_requires_admin(client, db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    admin = db_session.query(User).filter(User.email == "admin@example.com").first()
    if not admin:
        admin = User(
            email="admin@example.com", full_name="Admin User",
            role=UserRole.ADMIN, hashed_password=get_password_hash(PASSWORD),
        )
        user = User(
            email="regular@example.com", full_name="Regular User",
            role=UserRole.PARENT, hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add_all([admin, user])
        db_session.commit()

    user_token = _login(client, "regular@example.com")
    user_resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {user_token}"})
    assert user_resp.status_code == 403

    admin_token = _login(client, "admin@example.com")
    admin_resp = client.get("/api/admin/stats", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_resp.status_code == 200


# ── Admin users endpoint ──────────────────────────────────────

class TestAdminUsers:
    def test_list_all_users(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/users", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data
        assert "total" in data
        assert data["total"] >= 3  # at least admin, parent, student

    def test_filter_by_role(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/users?role=parent", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        for u in data["users"]:
            assert u["role"] == "parent"

    def test_search_by_name(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/users?search=Admin+Boss", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert any(u["email"] == users["admin"].email for u in data["users"])

    def test_pagination(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/users?skip=0&limit=1", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["users"]) <= 1
        assert data["total"] >= 3  # total is full count


# ── Admin permissions ─────────────────────────────────────────

class TestAdminPermissions:
    def test_parent_cannot_access_admin_users(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/admin/users", headers=headers)
        assert resp.status_code == 403

    def test_student_cannot_access_admin_users(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/admin/users", headers=headers)
        assert resp.status_code == 403


# ── Admin role management ────────────────────────────────────

class TestAdminRoleManagement:
    def test_add_teacher_role_to_parent(self, client, users):
        headers = _auth(client, users["admin"].email)
        parent = users["parent"]
        resp = client.post(
            f"/api/admin/users/{parent.id}/add-role",
            json={"role": "teacher"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "teacher" in data["roles"]
        assert "parent" in data["roles"]

    def test_remove_teacher_role_from_multi_role_user(self, client, users, db_session):
        headers = _auth(client, users["admin"].email)
        parent = users["parent"]
        # Ensure parent has teacher role (may have been added in previous test)
        from app.models.user import UserRole
        db_session.refresh(parent)
        if not parent.has_role(UserRole.TEACHER):
            client.post(
                f"/api/admin/users/{parent.id}/add-role",
                json={"role": "teacher"},
                headers=headers,
            )
        resp = client.post(
            f"/api/admin/users/{parent.id}/remove-role",
            json={"role": "teacher"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "teacher" not in data["roles"]
        assert "parent" in data["roles"]

    def test_cannot_remove_last_role(self, client, users):
        headers = _auth(client, users["admin"].email)
        student = users["student"]
        resp = client.post(
            f"/api/admin/users/{student.id}/remove-role",
            json={"role": "student"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "only role" in resp.json()["detail"].lower()

    def test_non_admin_cannot_add_role(self, client, users):
        headers = _auth(client, users["parent"].email)
        student = users["student"]
        resp = client.post(
            f"/api/admin/users/{student.id}/add-role",
            json={"role": "teacher"},
            headers=headers,
        )
        assert resp.status_code == 403


# ── Admin broadcast messaging ─────────────────────────────────

class TestAdminBroadcast:
    def test_send_broadcast(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.post(
            "/api/admin/broadcast",
            json={"subject": "Test Broadcast", "body": "Hello everyone!"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["subject"] == "Test Broadcast"
        assert data["recipient_count"] >= 3

    def test_list_broadcasts(self, client, users):
        headers = _auth(client, users["admin"].email)
        # Send one first
        client.post(
            "/api/admin/broadcast",
            json={"subject": "History Test", "body": "Body"},
            headers=headers,
        )
        resp = client.get("/api/admin/broadcasts", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "subject" in data[0]
        assert "recipient_count" in data[0]

    def test_non_admin_cannot_broadcast(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post(
            "/api/admin/broadcast",
            json={"subject": "Hack", "body": "Should fail"},
            headers=headers,
        )
        assert resp.status_code == 403


# ── Admin individual messaging ────────────────────────────────

class TestAdminMessage:
    def test_send_message_to_user(self, client, users):
        headers = _auth(client, users["admin"].email)
        student = users["student"]
        resp = client.post(
            f"/api/admin/users/{student.id}/message",
            json={"subject": "Hello Student", "body": "Please check your grades."},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_message_nonexistent_user(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.post(
            "/api/admin/users/99999/message",
            json={"subject": "Test", "body": "Body"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_non_admin_cannot_send_message(self, client, users):
        headers = _auth(client, users["parent"].email)
        student = users["student"]
        resp = client.post(
            f"/api/admin/users/{student.id}/message",
            json={"subject": "Hack", "body": "Should fail"},
            headers=headers,
        )
        assert resp.status_code == 403
