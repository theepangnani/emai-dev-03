import pytest

PASSWORD = "Password123!"


def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}


@pytest.fixture()
def notif_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "notif_user@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if user:
        return user
    user = User(
        email=email, full_name="Notif User", role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ── Original tests ────────────────────────────────────────────

def test_notifications_unread_and_mark_read(client, db_session):
    from app.core.security import get_password_hash
    from app.models.notification import Notification, NotificationType
    from app.models.user import User, UserRole

    user = db_session.query(User).filter(User.email == "notify@example.com").first()
    if not user:
        user = User(
            email="notify@example.com",
            full_name="Notify User",
            role=UserRole.PARENT,
            hashed_password=get_password_hash("Password123!"),
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

    token = _login(client, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    unread = client.get("/api/notifications/unread-count", headers=headers)
    assert unread.status_code == 200, unread.text
    assert unread.json()["count"] >= 1

    mark = client.put(f"/api/notifications/{notification.id}/read", headers=headers)
    assert mark.status_code == 200, mark.text


# ── List notifications ────────────────────────────────────────

class TestListNotifications:
    def test_list_returns_own_notifications(self, client, notif_user, db_session):
        from app.models.notification import Notification, NotificationType

        n = Notification(
            user_id=notif_user.id, type=NotificationType.SYSTEM,
            title="List Test", content="List test body", read=False,
        )
        db_session.add(n)
        db_session.commit()

        headers = _auth(client, notif_user.email)
        resp = client.get("/api/notifications/", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert any(item["title"] == "List Test" for item in resp.json())

    def test_list_unauthenticated_returns_401(self, client):
        resp = client.get("/api/notifications/")
        assert resp.status_code == 401


# ── Mark all read ─────────────────────────────────────────────

class TestMarkAllRead:
    def test_mark_all_read(self, client, notif_user, db_session):
        from app.models.notification import Notification, NotificationType

        for i in range(3):
            db_session.add(Notification(
                user_id=notif_user.id, type=NotificationType.SYSTEM,
                title=f"Bulk {i}", content="body", read=False,
            ))
        db_session.commit()

        headers = _auth(client, notif_user.email)
        resp = client.put("/api/notifications/read-all", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # Verify unread count is 0
        unread = client.get("/api/notifications/unread-count", headers=headers)
        assert unread.json()["count"] == 0


# ── Delete notification ───────────────────────────────────────

class TestDeleteNotification:
    def test_delete_own_notification(self, client, notif_user, db_session):
        from app.models.notification import Notification, NotificationType

        n = Notification(
            user_id=notif_user.id, type=NotificationType.SYSTEM,
            title="To Delete", content="body", read=False,
        )
        db_session.add(n)
        db_session.commit()
        db_session.refresh(n)

        headers = _auth(client, notif_user.email)
        resp = client.delete(f"/api/notifications/{n.id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_delete_nonexistent_returns_404(self, client, notif_user):
        headers = _auth(client, notif_user.email)
        resp = client.delete("/api/notifications/999999", headers=headers)
        assert resp.status_code == 404


# ── Notification settings ─────────────────────────────────────

# ── Acknowledge notification ──────────────────────────────────

class TestAcknowledgeNotification:
    def test_ack_sets_fields(self, client, notif_user, db_session):
        from app.models.notification import Notification, NotificationType

        n = Notification(
            user_id=notif_user.id, type=NotificationType.ASSIGNMENT_DUE,
            title="ACK Me", content="body", read=False,
            requires_ack=True, source_type="assignment", source_id=999,
        )
        db_session.add(n)
        db_session.commit()
        db_session.refresh(n)

        headers = _auth(client, notif_user.email)
        resp = client.put(f"/api/notifications/{n.id}/ack", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["acked_at"] is not None
        assert data["read"] is True
        assert data["requires_ack"] is True

    def test_ack_non_ack_notification_returns_400(self, client, notif_user, db_session):
        from app.models.notification import Notification, NotificationType

        n = Notification(
            user_id=notif_user.id, type=NotificationType.SYSTEM,
            title="No ACK", content="body", read=False,
            requires_ack=False,
        )
        db_session.add(n)
        db_session.commit()
        db_session.refresh(n)

        headers = _auth(client, notif_user.email)
        resp = client.put(f"/api/notifications/{n.id}/ack", headers=headers)
        assert resp.status_code == 400

    def test_ack_nonexistent_returns_404(self, client, notif_user):
        headers = _auth(client, notif_user.email)
        resp = client.put("/api/notifications/999999/ack", headers=headers)
        assert resp.status_code == 404


# ── Suppress notification ─────────────────────────────────────

class TestSuppressNotification:
    def test_suppress_creates_suppression_row(self, client, notif_user, db_session):
        from app.models.notification import Notification, NotificationType
        from app.models.notification_suppression import NotificationSuppression

        n = Notification(
            user_id=notif_user.id, type=NotificationType.ASSIGNMENT_DUE,
            title="Suppress Me", content="body", read=False,
            requires_ack=True, source_type="assignment", source_id=888,
        )
        db_session.add(n)
        db_session.commit()
        db_session.refresh(n)

        headers = _auth(client, notif_user.email)
        resp = client.put(f"/api/notifications/{n.id}/suppress", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["acked_at"] is not None
        assert data["read"] is True

        # Verify suppression row exists
        suppression = db_session.query(NotificationSuppression).filter(
            NotificationSuppression.user_id == notif_user.id,
            NotificationSuppression.source_type == "assignment",
            NotificationSuppression.source_id == 888,
        ).first()
        assert suppression is not None

    def test_suppress_no_source_returns_400(self, client, notif_user, db_session):
        from app.models.notification import Notification, NotificationType

        n = Notification(
            user_id=notif_user.id, type=NotificationType.SYSTEM,
            title="No Source", content="body", read=False,
        )
        db_session.add(n)
        db_session.commit()
        db_session.refresh(n)

        headers = _auth(client, notif_user.email)
        resp = client.put(f"/api/notifications/{n.id}/suppress", headers=headers)
        assert resp.status_code == 400

    def test_suppress_idempotent_on_repeat(self, client, notif_user, db_session):
        from app.models.notification import Notification, NotificationType
        from app.models.notification_suppression import NotificationSuppression

        n1 = Notification(
            user_id=notif_user.id, type=NotificationType.ASSIGNMENT_DUE,
            title="Suppress First", content="body", read=False,
            requires_ack=True, source_type="assignment", source_id=777,
        )
        n2 = Notification(
            user_id=notif_user.id, type=NotificationType.ASSIGNMENT_DUE,
            title="Suppress Second", content="body", read=False,
            requires_ack=True, source_type="assignment", source_id=777,
        )
        db_session.add_all([n1, n2])
        db_session.commit()
        db_session.refresh(n1)
        db_session.refresh(n2)

        headers = _auth(client, notif_user.email)
        resp1 = client.put(f"/api/notifications/{n1.id}/suppress", headers=headers)
        assert resp1.status_code == 200

        # Second suppress on same source should still succeed (idempotent)
        resp2 = client.put(f"/api/notifications/{n2.id}/suppress", headers=headers)
        assert resp2.status_code == 200

        # Only one suppression row
        count = db_session.query(NotificationSuppression).filter(
            NotificationSuppression.user_id == notif_user.id,
            NotificationSuppression.source_type == "assignment",
            NotificationSuppression.source_id == 777,
        ).count()
        assert count == 1


# ── Notification response schema ──────────────────────────────

class TestNotificationResponseSchema:
    def test_list_includes_ack_fields(self, client, notif_user, db_session):
        from app.models.notification import Notification, NotificationType

        n = Notification(
            user_id=notif_user.id, type=NotificationType.ASSIGNMENT_DUE,
            title="Schema Test", content="body", read=False,
            requires_ack=True, source_type="assignment", source_id=555,
            reminder_count=1,
        )
        db_session.add(n)
        db_session.commit()

        headers = _auth(client, notif_user.email)
        resp = client.get("/api/notifications/", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        schema_item = next((i for i in items if i["title"] == "Schema Test"), None)
        assert schema_item is not None
        assert schema_item["requires_ack"] is True
        assert schema_item["source_type"] == "assignment"
        assert schema_item["source_id"] == 555
        assert schema_item["reminder_count"] == 1
        assert schema_item["acked_at"] is None


# ── Notification settings ─────────────────────────────────────

class TestNotificationSettings:
    def test_get_settings(self, client, notif_user):
        headers = _auth(client, notif_user.email)
        resp = client.get("/api/notifications/settings", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "email_notifications" in data
        assert "assignment_reminder_days" in data
        assert "task_reminder_days" in data

    def test_update_settings(self, client, notif_user):
        headers = _auth(client, notif_user.email)
        resp = client.put("/api/notifications/settings", json={
            "email_notifications": False,
            "assignment_reminder_days": "1,7",
            "task_reminder_days": "1,2,5",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email_notifications"] is False
        assert data["assignment_reminder_days"] == "1,7"
        assert data["task_reminder_days"] == "1,2,5"

        # Verify persistence
        get_resp = client.get("/api/notifications/settings", headers=headers)
        assert get_resp.json()["email_notifications"] is False
        assert get_resp.json()["assignment_reminder_days"] == "1,7"
        assert get_resp.json()["task_reminder_days"] == "1,2,5"
