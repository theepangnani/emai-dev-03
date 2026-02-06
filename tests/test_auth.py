def test_register_login_me(client):
    payload = {
        "email": "testuser@example.com",
        "password": "password123!",
        "full_name": "Test User",
        "role": "parent",
    }
    register = client.post("/api/auth/register", json=payload)
    assert register.status_code == 200, register.text

    login = client.post(
        "/api/auth/login",
        data={"username": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]

    me = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["email"] == payload["email"]
    assert body["role"] == payload["role"]


def test_login_rejects_invalid_password(client, db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email="loginfail@example.com",
        full_name="Login Fail",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("password123!"),
    )
    db_session.add(user)
    db_session.commit()

    login = client.post(
        "/api/auth/login",
        data={"username": user.email, "password": "wrong-password"},
    )
    assert login.status_code == 401
