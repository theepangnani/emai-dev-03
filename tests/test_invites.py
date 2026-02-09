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

    parent = db_session.query(User).filter(User.email == "inv_parent@test.com").first()
    if parent:
        teacher = db_session.query(User).filter(User.email == "inv_teacher@test.com").first()
        student = db_session.query(User).filter(User.email == "inv_student@test.com").first()
        admin = db_session.query(User).filter(User.email == "inv_admin@test.com").first()
        return {"parent": parent, "teacher": teacher, "student": student, "admin": admin}

    hashed = get_password_hash(PASSWORD)
    parent = User(email="inv_parent@test.com", full_name="Inv Parent", role=UserRole.PARENT, hashed_password=hashed)
    teacher = User(email="inv_teacher@test.com", full_name="Inv Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    student = User(email="inv_student@test.com", full_name="Inv Student", role=UserRole.STUDENT, hashed_password=hashed)
    admin = User(email="inv_admin@test.com", full_name="Inv Admin", role=UserRole.ADMIN, hashed_password=hashed)
    db_session.add_all([parent, teacher, student, admin])
    db_session.commit()
    for u in [parent, teacher, student, admin]:
        db_session.refresh(u)
    return {"parent": parent, "teacher": teacher, "student": student, "admin": admin}


# ── Create invite ─────────────────────────────────────────────

class TestCreateInvite:
    def test_parent_invites_student(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/invites/", json={
            "email": "inv_new_student@test.com", "invite_type": "student",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "inv_new_student@test.com"
        assert data["invite_type"] == "student"
        assert data["token"] is not None

    def test_teacher_invites_teacher(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.post("/api/invites/", json={
            "email": "inv_new_teacher@test.com", "invite_type": "teacher",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["invite_type"] == "teacher"

    def test_admin_invites_teacher(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.post("/api/invites/", json={
            "email": "inv_admin_teacher@test.com", "invite_type": "teacher",
        }, headers=headers)
        assert resp.status_code == 200

    def test_student_cannot_invite(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.post("/api/invites/", json={
            "email": "inv_student_invite@test.com", "invite_type": "student",
        }, headers=headers)
        assert resp.status_code == 403

    def test_parent_cannot_invite_teacher(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/invites/", json={
            "email": "inv_par_teacher@test.com", "invite_type": "teacher",
        }, headers=headers)
        assert resp.status_code == 403

    def test_existing_email_rejected(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/invites/", json={
            "email": users["student"].email, "invite_type": "student",
        }, headers=headers)
        assert resp.status_code == 400
        assert "already exists" in resp.json()["detail"].lower()

    def test_duplicate_pending_rejected(self, client, users):
        headers = _auth(client, users["parent"].email)
        email = "inv_dup_pending@test.com"
        # First invite
        resp1 = client.post("/api/invites/", json={
            "email": email, "invite_type": "student",
        }, headers=headers)
        assert resp1.status_code == 200

        # Second invite same email
        resp2 = client.post("/api/invites/", json={
            "email": email, "invite_type": "student",
        }, headers=headers)
        assert resp2.status_code == 400
        assert "pending" in resp2.json()["detail"].lower()

    def test_metadata_stored(self, client, users):
        headers = _auth(client, users["parent"].email)
        resp = client.post("/api/invites/", json={
            "email": "inv_meta@test.com", "invite_type": "student",
            "metadata": {"relationship_type": "mother"},
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["metadata_json"]["relationship_type"] == "mother"


# ── List sent invites ─────────────────────────────────────────

class TestListSentInvites:
    def test_list_own(self, client, users):
        headers = _auth(client, users["parent"].email)
        # Ensure at least one invite exists
        client.post("/api/invites/", json={
            "email": "inv_listable@test.com", "invite_type": "student",
        }, headers=headers)

        resp = client.get("/api/invites/sent", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_doesnt_show_others(self, client, users):
        headers = _auth(client, users["teacher"].email)
        resp = client.get("/api/invites/sent", headers=headers)
        assert resp.status_code == 200
        for invite in resp.json():
            assert invite["invited_by_user_id"] == users["teacher"].id

    def test_empty_list(self, client, users, db_session):
        """A user who hasn't sent invites should see an empty list."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        email = "inv_empty@test.com"
        u = db_session.query(User).filter(User.email == email).first()
        if not u:
            u = User(email=email, full_name="No Invites", role=UserRole.PARENT,
                     hashed_password=get_password_hash(PASSWORD))
            db_session.add(u)
            db_session.commit()

        headers = _auth(client, email)
        resp = client.get("/api/invites/sent", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []


# ── Permissions ───────────────────────────────────────────────

class TestInvitePermissions:
    def test_unauthenticated_rejected(self, client):
        resp = client.post("/api/invites/", json={
            "email": "inv_noauth@test.com", "invite_type": "student",
        })
        assert resp.status_code == 401
