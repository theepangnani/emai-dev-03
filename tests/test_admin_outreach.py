"""Tests for Outreach Send, Log, and Stats API."""
import pytest
from unittest.mock import patch, MagicMock
from conftest import PASSWORD, _auth


@pytest.fixture()
def admin_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "outreach_admin@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name="Outreach Admin",
            role=UserRole.ADMIN,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture()
def admin_headers(client, admin_user):
    return _auth(client, admin_user.email)


@pytest.fixture()
def contact_with_email(client, admin_headers):
    resp = client.post("/api/admin/contacts", json={
        "full_name": "Email Contact",
        "email": "outreach.target@example.com",
        "status": "lead",
        "source": "manual",
    }, headers=admin_headers)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture()
def contact_without_email(client, admin_headers):
    resp = client.post("/api/admin/contacts", json={
        "full_name": "No Email Contact",
        "phone": "+14165559999",
        "status": "lead",
        "source": "manual",
    }, headers=admin_headers)
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture()
def template(client, admin_headers):
    resp = client.post("/api/admin/outreach-templates", json={
        "name": "Outreach Test Tpl",
        "subject": "Hello {{full_name}}",
        "body_text": "Hi {{full_name}}, check out ClassBridge!",
        "template_type": "email",
        "variables": ["full_name"],
    }, headers=admin_headers)
    assert resp.status_code == 201
    return resp.json()


class TestOutreachSend:
    @patch("app.services.outreach_service.send_email_sync", return_value=True)
    @patch("app.services.outreach_service.wrap_branded_email", return_value="<html>branded</html>")
    def test_send_email_success(self, mock_wrap, mock_send, client, admin_headers, contact_with_email, template):
        resp = client.post("/api/admin/outreach/send", json={
            "parent_contact_ids": [contact_with_email["id"]],
            "channel": "email",
            "template_id": template["id"],
        }, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent_count"] == 1
        assert data["failed_count"] == 0
        mock_send.assert_called_once()

    @patch("app.services.outreach_service.send_email_sync", return_value=True)
    @patch("app.services.outreach_service.wrap_branded_email", return_value="<html>branded</html>")
    def test_send_email_no_email_address(self, mock_wrap, mock_send, client, admin_headers, contact_without_email):
        resp = client.post("/api/admin/outreach/send", json={
            "parent_contact_ids": [contact_without_email["id"]],
            "channel": "email",
            "custom_subject": "Hello",
            "custom_body": "Hi there",
        }, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent_count"] == 0
        assert data["failed_count"] == 1
        assert len(data["errors"]) == 1
        assert "No email" in data["errors"][0]["error"]

    @patch("app.services.outreach_service.is_twilio_configured", return_value=False)
    def test_whatsapp_not_configured(self, mock_twilio, client, admin_headers, contact_with_email):
        resp = client.post("/api/admin/outreach/send", json={
            "parent_contact_ids": [contact_with_email["id"]],
            "channel": "whatsapp",
            "custom_body": "Hi",
        }, headers=admin_headers)
        assert resp.status_code == 503

    @patch("app.services.outreach_service.send_email_sync", return_value=True)
    @patch("app.services.outreach_service.wrap_branded_email", return_value="<html></html>")
    def test_send_creates_outreach_log(self, mock_wrap, mock_send, client, admin_headers, contact_with_email):
        client.post("/api/admin/outreach/send", json={
            "parent_contact_ids": [contact_with_email["id"]],
            "channel": "email",
            "custom_subject": "Test Log",
            "custom_body": "Log body",
        }, headers=admin_headers)
        # Verify log entry
        resp = client.get(
            f"/api/admin/outreach/log?contact_id={contact_with_email['id']}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["items"][0]["channel"] == "email"

    @patch("app.services.outreach_service.send_email_sync", return_value=False)
    @patch("app.services.outreach_service.wrap_branded_email", return_value="<html></html>")
    def test_send_email_failure_logged(self, mock_wrap, mock_send, client, admin_headers, contact_with_email):
        resp = client.post("/api/admin/outreach/send", json={
            "parent_contact_ids": [contact_with_email["id"]],
            "channel": "email",
            "custom_subject": "Fail",
            "custom_body": "Will fail",
        }, headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["failed_count"] == 1

    def test_send_no_contacts_found(self, client, admin_headers):
        resp = client.post("/api/admin/outreach/send", json={
            "parent_contact_ids": [999998, 999999],
            "channel": "email",
            "custom_subject": "Hi",
            "custom_body": "Body",
        }, headers=admin_headers)
        assert resp.status_code == 400


class TestOutreachLog:
    @patch("app.services.outreach_service.send_email_sync", return_value=True)
    @patch("app.services.outreach_service.wrap_branded_email", return_value="<html></html>")
    def test_list_logs(self, mock_wrap, mock_send, client, admin_headers, contact_with_email):
        # Send one message to create a log
        client.post("/api/admin/outreach/send", json={
            "parent_contact_ids": [contact_with_email["id"]],
            "channel": "email",
            "custom_subject": "Log List",
            "custom_body": "Body",
        }, headers=admin_headers)
        resp = client.get("/api/admin/outreach/log", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    @patch("app.services.outreach_service.send_email_sync", return_value=True)
    @patch("app.services.outreach_service.wrap_branded_email", return_value="<html></html>")
    def test_get_single_log(self, mock_wrap, mock_send, client, admin_headers, contact_with_email):
        client.post("/api/admin/outreach/send", json={
            "parent_contact_ids": [contact_with_email["id"]],
            "channel": "email",
            "custom_subject": "Single Log",
            "custom_body": "Single body",
        }, headers=admin_headers)
        # Get list, then fetch first entry
        list_resp = client.get("/api/admin/outreach/log", headers=admin_headers)
        log_id = list_resp.json()["items"][0]["id"]
        resp = client.get(f"/api/admin/outreach/log/{log_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == log_id

    def test_get_nonexistent_log(self, client, admin_headers):
        resp = client.get("/api/admin/outreach/log/999999", headers=admin_headers)
        assert resp.status_code == 404


class TestOutreachStats:
    def test_stats_endpoint(self, client, admin_headers):
        resp = client.get("/api/admin/outreach/stats", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_sent" in data
        assert "sent_today" in data
        assert "sent_this_week" in data
        assert "by_channel" in data
        assert "by_status" in data
