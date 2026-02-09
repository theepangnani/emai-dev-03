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
