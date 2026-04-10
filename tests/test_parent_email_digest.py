"""Comprehensive tests for parent email digest endpoints (#2654, #2967)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest
from conftest import PASSWORD, _auth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PARENT_EMAIL = "digest_parent@test.com"
STUDENT_EMAIL = "digest_student@test.com"
TEACHER_EMAIL = "digest_teacher@test.com"

PREFIX = "/api/parent/email-digest"


@pytest.fixture()
def setup(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.parent_gmail_integration import (
        ParentGmailIntegration,
        ParentDigestSettings,
        DigestDeliveryLog,
    )

    parent = db_session.query(User).filter(User.email == PARENT_EMAIL).first()
    if parent:
        integration = (
            db_session.query(ParentGmailIntegration)
            .filter(ParentGmailIntegration.parent_id == parent.id)
            .first()
        )
        student = db_session.query(User).filter(User.email == STUDENT_EMAIL).first()
        teacher = db_session.query(User).filter(User.email == TEACHER_EMAIL).first()
        log = (
            db_session.query(DigestDeliveryLog)
            .filter(DigestDeliveryLog.parent_id == parent.id)
            .first()
        )
        return {
            "parent": parent,
            "student": student,
            "teacher": teacher,
            "integration": integration,
            "settings": integration.digest_settings if integration else None,
            "log": log,
        }

    hashed = get_password_hash(PASSWORD)
    parent = User(email=PARENT_EMAIL, full_name="Digest Parent", role=UserRole.PARENT, hashed_password=hashed)
    student = User(email=STUDENT_EMAIL, full_name="Digest Student", role=UserRole.STUDENT, hashed_password=hashed)
    teacher = User(email=TEACHER_EMAIL, full_name="Digest Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    db_session.add_all([parent, student, teacher])
    db_session.flush()

    integration = ParentGmailIntegration(
        parent_id=parent.id,
        gmail_address="parent@gmail.com",
        google_id="google123",
        access_token="enc_access",
        refresh_token="enc_refresh",
        child_school_email="child@school.ca",
        child_first_name="Alex",
    )
    db_session.add(integration)
    db_session.flush()

    digest_settings = ParentDigestSettings(integration_id=integration.id)
    db_session.add(digest_settings)
    db_session.flush()

    log = DigestDeliveryLog(
        parent_id=parent.id,
        integration_id=integration.id,
        email_count=5,
        digest_content="Your child received 5 emails today.",
        digest_length_chars=42,
        channels_used="in_app,email",
        status="delivered",
    )
    db_session.add(log)
    db_session.commit()

    return {
        "parent": parent,
        "student": student,
        "teacher": teacher,
        "integration": integration,
        "settings": digest_settings,
        "log": log,
    }


# ---------------------------------------------------------------------------
# Integration CRUD
# ---------------------------------------------------------------------------


class TestListIntegrations:
    def test_list_returns_integrations(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/integrations", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["gmail_address"] == "parent@gmail.com"

    def test_list_unauthenticated(self, client, setup):
        resp = client.get(f"{PREFIX}/integrations")
        assert resp.status_code in (401, 403)

    def test_list_wrong_role(self, client, setup):
        headers = _auth(client, STUDENT_EMAIL)
        resp = client.get(f"{PREFIX}/integrations", headers=headers)
        assert resp.status_code == 403


class TestGetIntegration:
    def test_get_own_integration(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.get(f"{PREFIX}/integrations/{iid}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == iid
        assert resp.json()["child_first_name"] == "Alex"

    def test_get_nonexistent(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/integrations/99999", headers=headers)
        assert resp.status_code == 404

    def test_get_unauthenticated(self, client, setup):
        resp = client.get(f"{PREFIX}/integrations/{setup['integration'].id}")
        assert resp.status_code in (401, 403)

    def test_get_wrong_role(self, client, setup):
        headers = _auth(client, TEACHER_EMAIL)
        resp = client.get(f"{PREFIX}/integrations/{setup['integration'].id}", headers=headers)
        assert resp.status_code == 403


class TestUpdateIntegration:
    def test_update_child_info(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.patch(f"{PREFIX}/integrations/{iid}", json={
            "child_first_name": "Jordan",
            "child_school_email": "jordan@school.ca",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["child_first_name"] == "Jordan"
        assert resp.json()["child_school_email"] == "jordan@school.ca"

    def test_update_nonexistent(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.patch(f"{PREFIX}/integrations/99999", json={
            "child_first_name": "Nobody",
        }, headers=headers)
        assert resp.status_code == 404


class TestDeleteIntegration:
    def test_delete_own_integration(self, client, db_session, setup):
        """Create a separate integration then delete it."""
        from app.models.parent_gmail_integration import ParentGmailIntegration, ParentDigestSettings

        tmp = ParentGmailIntegration(
            parent_id=setup["parent"].id,
            gmail_address="temp@gmail.com",
            google_id="temp_gid",
            access_token="t",
            refresh_token="t",
            child_school_email="temp@school.ca",
        )
        db_session.add(tmp)
        db_session.flush()
        tmp_settings = ParentDigestSettings(integration_id=tmp.id)
        db_session.add(tmp_settings)
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.delete(f"{PREFIX}/integrations/{tmp.id}", headers=headers)
        assert resp.status_code == 204

    def test_delete_nonexistent(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.delete(f"{PREFIX}/integrations/99999", headers=headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Digest Settings
# ---------------------------------------------------------------------------


class TestGetSettings:
    def test_get_settings(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.get(f"{PREFIX}/settings/{iid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["integration_id"] == iid
        assert data["digest_enabled"] is True
        assert data["delivery_time"] == "07:00"
        assert data["timezone"] == "America/Toronto"

    def test_get_settings_nonexistent(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/settings/99999", headers=headers)
        assert resp.status_code == 404

    def test_get_settings_unauthenticated(self, client, setup):
        resp = client.get(f"{PREFIX}/settings/{setup['integration'].id}")
        assert resp.status_code in (401, 403)


class TestUpdateSettings:
    def test_update_delivery_time(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.put(f"{PREFIX}/settings/{iid}", json={
            "delivery_time": "18:30",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["delivery_time"] == "18:30"

    def test_update_invalid_delivery_time(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.put(f"{PREFIX}/settings/{iid}", json={
            "delivery_time": "25:00",
        }, headers=headers)
        assert resp.status_code == 422

    def test_update_timezone(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.put(f"{PREFIX}/settings/{iid}", json={
            "timezone": "US/Eastern",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["timezone"] == "US/Eastern"

    def test_update_invalid_timezone(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.put(f"{PREFIX}/settings/{iid}", json={
            "timezone": "Mars/Olympus",
        }, headers=headers)
        assert resp.status_code == 422

    def test_update_digest_format(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.put(f"{PREFIX}/settings/{iid}", json={
            "digest_format": "brief",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["digest_format"] == "brief"

    def test_update_delivery_channels(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.put(f"{PREFIX}/settings/{iid}", json={
            "delivery_channels": "in_app",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["delivery_channels"] == "in_app"

    def test_update_settings_nonexistent(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.put(f"{PREFIX}/settings/99999", json={
            "delivery_time": "09:00",
        }, headers=headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Delivery Logs
# ---------------------------------------------------------------------------


class TestListLogs:
    def test_list_logs(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/logs", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["status"] == "delivered"

    def test_list_logs_pagination(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/logs?skip=0&limit=1", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) <= 1

    def test_list_logs_filter_by_integration(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.get(f"{PREFIX}/logs?integration_id={iid}", headers=headers)
        assert resp.status_code == 200

    def test_list_logs_unauthenticated(self, client, setup):
        resp = client.get(f"{PREFIX}/logs")
        assert resp.status_code in (401, 403)


class TestGetLog:
    def test_get_log(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        log_id = setup["log"].id
        resp = client.get(f"{PREFIX}/logs/{log_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["email_count"] == 5
        assert "5 emails" in resp.json()["digest_content"]

    def test_get_log_nonexistent(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/logs/99999", headers=headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Pause / Resume
# ---------------------------------------------------------------------------


class TestPauseResume:
    def test_pause_integration(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(f"{PREFIX}/integrations/{iid}/pause", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["paused_until"] is not None

    def test_pause_with_date(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        future = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
        resp = client.post(f"{PREFIX}/integrations/{iid}/pause", params={"paused_until": future}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["paused_until"] is not None

    def test_resume_integration(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        # Pause first
        client.post(f"{PREFIX}/integrations/{iid}/pause", headers=headers)
        # Resume
        resp = client.post(f"{PREFIX}/integrations/{iid}/resume", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["paused_until"] is None

    def test_pause_nonexistent(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(f"{PREFIX}/integrations/99999/pause", headers=headers)
        assert resp.status_code == 404

    def test_resume_nonexistent(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(f"{PREFIX}/integrations/99999/resume", headers=headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# WhatsApp OTP (#2967)
# ---------------------------------------------------------------------------


class TestWhatsAppSendOTP:
    @patch("app.services.whatsapp_service.is_whatsapp_enabled", return_value=True)
    @patch("app.services.whatsapp_service.send_otp", return_value=True)
    @patch("app.services.whatsapp_service.generate_otp", return_value="123456")
    def test_send_otp_success(self, mock_gen, mock_send, mock_enabled, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(f"{PREFIX}/integrations/{iid}/whatsapp/send-otp", json={
            "phone": "+14165551234",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["phone"] == "+14165551234"

    def test_send_otp_invalid_phone(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(f"{PREFIX}/integrations/{iid}/whatsapp/send-otp", json={
            "phone": "4165551234",
        }, headers=headers)
        assert resp.status_code == 422

    @patch("app.services.whatsapp_service.is_whatsapp_enabled", return_value=False)
    def test_send_otp_not_configured(self, mock_enabled, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(f"{PREFIX}/integrations/{iid}/whatsapp/send-otp", json={
            "phone": "+14165551234",
        }, headers=headers)
        assert resp.status_code == 503

    def test_send_otp_nonexistent_integration(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(f"{PREFIX}/integrations/99999/whatsapp/send-otp", json={
            "phone": "+14165551234",
        }, headers=headers)
        assert resp.status_code == 404

    def test_send_otp_unauthenticated(self, client, setup):
        iid = setup["integration"].id
        resp = client.post(f"{PREFIX}/integrations/{iid}/whatsapp/send-otp", json={
            "phone": "+14165551234",
        })
        assert resp.status_code in (401, 403)

    def test_send_otp_wrong_role(self, client, setup):
        headers = _auth(client, STUDENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(f"{PREFIX}/integrations/{iid}/whatsapp/send-otp", json={
            "phone": "+14165551234",
        }, headers=headers)
        assert resp.status_code == 403


class TestWhatsAppVerifyOTP:
    def test_verify_otp_correct(self, client, db_session, setup):
        """Set OTP directly in DB, then verify via endpoint."""
        integration = setup["integration"]
        integration.whatsapp_phone = "+14165551234"
        integration.whatsapp_otp_code = "654321"
        integration.whatsapp_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        integration.whatsapp_verified = False
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(f"{PREFIX}/integrations/{integration.id}/whatsapp/verify-otp", json={
            "otp_code": "654321",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["message"] == "WhatsApp verified successfully"
        assert resp.json()["phone"] == "+14165551234"

    def test_verify_otp_wrong_code(self, client, db_session, setup):
        integration = setup["integration"]
        integration.whatsapp_otp_code = "111111"
        integration.whatsapp_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(f"{PREFIX}/integrations/{integration.id}/whatsapp/verify-otp", json={
            "otp_code": "999999",
        }, headers=headers)
        assert resp.status_code == 400
        assert "Invalid OTP" in resp.json()["detail"]

    def test_verify_otp_expired(self, client, db_session, setup):
        integration = setup["integration"]
        integration.whatsapp_otp_code = "222222"
        integration.whatsapp_otp_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(f"{PREFIX}/integrations/{integration.id}/whatsapp/verify-otp", json={
            "otp_code": "222222",
        }, headers=headers)
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()

    def test_verify_otp_no_pending(self, client, db_session, setup):
        integration = setup["integration"]
        integration.whatsapp_otp_code = None
        integration.whatsapp_otp_expires_at = None
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(f"{PREFIX}/integrations/{integration.id}/whatsapp/verify-otp", json={
            "otp_code": "123456",
        }, headers=headers)
        assert resp.status_code == 400
        assert "No OTP pending" in resp.json()["detail"]

    def test_verify_otp_nonexistent(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(f"{PREFIX}/integrations/99999/whatsapp/verify-otp", json={
            "otp_code": "123456",
        }, headers=headers)
        assert resp.status_code == 404

    def test_verify_otp_invalid_format(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(f"{PREFIX}/integrations/{iid}/whatsapp/verify-otp", json={
            "otp_code": "abc",
        }, headers=headers)
        assert resp.status_code == 422

    def test_verify_adds_whatsapp_channel(self, client, db_session, setup):
        """After OTP verify, whatsapp should appear in delivery_channels."""
        integration = setup["integration"]
        # Reset channels to not include whatsapp
        if integration.digest_settings:
            integration.digest_settings.delivery_channels = "in_app,email"
        integration.whatsapp_phone = "+14165559999"
        integration.whatsapp_otp_code = "777777"
        integration.whatsapp_otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        integration.whatsapp_verified = False
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        client.post(f"{PREFIX}/integrations/{integration.id}/whatsapp/verify-otp", json={
            "otp_code": "777777",
        }, headers=headers)

        # Check channels
        resp = client.get(f"{PREFIX}/settings/{integration.id}", headers=headers)
        assert resp.status_code == 200
        assert "whatsapp" in resp.json()["delivery_channels"]


class TestWhatsAppDisconnect:
    def test_disconnect_whatsapp(self, client, db_session, setup):
        integration = setup["integration"]
        integration.whatsapp_phone = "+14165551234"
        integration.whatsapp_verified = True
        if integration.digest_settings:
            integration.digest_settings.delivery_channels = "in_app,email,whatsapp"
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.delete(f"{PREFIX}/integrations/{integration.id}/whatsapp", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["message"] == "WhatsApp disconnected"

        # Verify fields cleared
        resp2 = client.get(f"{PREFIX}/integrations/{integration.id}", headers=headers)
        assert resp2.json()["whatsapp_phone"] is None
        assert resp2.json()["whatsapp_verified"] is False

    def test_disconnect_removes_channel(self, client, db_session, setup):
        integration = setup["integration"]
        if integration.digest_settings:
            integration.digest_settings.delivery_channels = "in_app,email,whatsapp"
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        client.delete(f"{PREFIX}/integrations/{integration.id}/whatsapp", headers=headers)

        resp = client.get(f"{PREFIX}/settings/{integration.id}", headers=headers)
        assert resp.status_code == 200
        assert "whatsapp" not in resp.json()["delivery_channels"]

    def test_disconnect_nonexistent(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.delete(f"{PREFIX}/integrations/99999/whatsapp", headers=headers)
        assert resp.status_code == 404

    def test_disconnect_unauthenticated(self, client, setup):
        resp = client.delete(f"{PREFIX}/integrations/{setup['integration'].id}/whatsapp")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Auth / role guard checks
# ---------------------------------------------------------------------------


class TestAuthGuards:
    """Verify all endpoints reject unauthenticated or wrong-role users."""

    def test_student_cannot_access_integrations(self, client, setup):
        headers = _auth(client, STUDENT_EMAIL)
        assert client.get(f"{PREFIX}/integrations", headers=headers).status_code == 403

    def test_teacher_cannot_access_settings(self, client, setup):
        headers = _auth(client, TEACHER_EMAIL)
        iid = setup["integration"].id
        assert client.get(f"{PREFIX}/settings/{iid}", headers=headers).status_code == 403

    def test_student_cannot_access_logs(self, client, setup):
        headers = _auth(client, STUDENT_EMAIL)
        assert client.get(f"{PREFIX}/logs", headers=headers).status_code == 403

    def test_teacher_cannot_pause(self, client, setup):
        headers = _auth(client, TEACHER_EMAIL)
        iid = setup["integration"].id
        assert client.post(f"{PREFIX}/integrations/{iid}/pause", headers=headers).status_code == 403

    def test_student_cannot_resume(self, client, setup):
        headers = _auth(client, STUDENT_EMAIL)
        iid = setup["integration"].id
        assert client.post(f"{PREFIX}/integrations/{iid}/resume", headers=headers).status_code == 403

    def test_teacher_cannot_delete_whatsapp(self, client, setup):
        headers = _auth(client, TEACHER_EMAIL)
        iid = setup["integration"].id
        assert client.delete(f"{PREFIX}/integrations/{iid}/whatsapp", headers=headers).status_code == 403


# ---------------------------------------------------------------------------
# Response schema checks
# ---------------------------------------------------------------------------


class TestResponseSchema:
    def test_integration_response_has_whatsapp_fields(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.get(f"{PREFIX}/integrations/{iid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "whatsapp_phone" in data
        assert "whatsapp_verified" in data
