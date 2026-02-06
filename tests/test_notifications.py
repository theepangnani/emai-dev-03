def _login(client, email, password):
    resp = client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_notifications_unread_and_mark_read(client, db_session):
    from app.core.security import get_password_hash
    from app.models.notification import Notification, NotificationType
    from app.models.user import User, UserRole

    user = User(
        email="notify@example.com",
        full_name="Notify User",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("password123!"),
    )
    db_session.add(user)
    db_session.commit()

    notification = Notification(
        user_id=user.id,
        type=NotificationType.MESSAGE,
        title="New message",
        content="Test message",
        read=False,
    )
    db_session.add(notification)
    db_session.commit()

    token = _login(client, user.email, "password123!")
    headers = {"Authorization": f"Bearer {token}"}

    unread = client.get("/api/notifications/unread-count", headers=headers)
    assert unread.status_code == 200, unread.text
    assert unread.json()["count"] == 1

    mark = client.put(f"/api/notifications/{notification.id}/read", headers=headers)
    assert mark.status_code == 200, mark.text

    unread_after = client.get("/api/notifications/unread-count", headers=headers)
    assert unread_after.status_code == 200, unread_after.text
    assert unread_after.json()["count"] == 0
