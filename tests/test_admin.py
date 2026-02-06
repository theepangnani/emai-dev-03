def _login(client, email, password):
    resp = client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_admin_stats_requires_admin(client, db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    admin = User(
        email="admin@example.com",
        full_name="Admin User",
        role=UserRole.ADMIN,
        hashed_password=get_password_hash("password123!"),
    )
    user = User(
        email="regular@example.com",
        full_name="Regular User",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("password123!"),
    )
    db_session.add_all([admin, user])
    db_session.commit()

    user_token = _login(client, user.email, "password123!")
    user_resp = client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert user_resp.status_code == 403

    admin_token = _login(client, admin.email, "password123!")
    admin_resp = client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_resp.status_code == 200
