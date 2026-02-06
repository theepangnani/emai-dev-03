def _login(client, email, password):
    resp = client.post("/api/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def test_unread_count_and_mark_read(client, db_session):
    from app.core.security import get_password_hash
    from app.models.message import Conversation, Message
    from app.models.user import User, UserRole

    user_a = User(
        email="usera@example.com",
        full_name="User A",
        role=UserRole.PARENT,
        hashed_password=get_password_hash("password123!"),
    )
    user_b = User(
        email="userb@example.com",
        full_name="User B",
        role=UserRole.TEACHER,
        hashed_password=get_password_hash("password123!"),
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()

    conv = Conversation(
        participant_1_id=user_a.id,
        participant_2_id=user_b.id,
        subject="Test conversation",
    )
    db_session.add(conv)
    db_session.commit()

    msg = Message(
        conversation_id=conv.id,
        sender_id=user_b.id,
        content="Hello from B",
        is_read=False,
    )
    db_session.add(msg)
    db_session.commit()

    token = _login(client, user_a.email, "password123!")
    headers = {"Authorization": f"Bearer {token}"}

    unread = client.get("/api/messages/unread-count", headers=headers)
    assert unread.status_code == 200, unread.text
    assert unread.json()["total_unread"] == 1

    mark = client.patch(f"/api/messages/conversations/{conv.id}/read", headers=headers)
    assert mark.status_code == 200, mark.text

    unread_after = client.get("/api/messages/unread-count", headers=headers)
    assert unread_after.status_code == 200, unread_after.text
    assert unread_after.json()["total_unread"] == 0
