"""Comprehensive tests for parent email digest endpoints (#2654, #2967, #3178)."""

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

    def test_default_digest_format_is_sectioned(self, db_session):
        """#4484, #4485 — new ParentDigestSettings rows default to 'sectioned'.

        The sectioned path enforces ≤3 items per section + 'And N more' CTA
        + Urgent-first ordering, killing both the 3-item-cap bypass (#4484)
        and the Quick-Note-renders-at-bottom defect (#4485)."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.models.parent_gmail_integration import (
            ParentGmailIntegration,
            ParentDigestSettings,
        )

        # Use a unique email so this test is independent of `setup`.
        parent = User(
            email="default_format_parent@test.com",
            full_name="Default Format Parent",
            role=UserRole.PARENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(parent)
        db_session.flush()

        integration = ParentGmailIntegration(
            parent_id=parent.id,
            gmail_address="default_format@gmail.com",
            google_id="default_format_gid",
            access_token="t",
            refresh_token="t",
            child_school_email="default_format_child@school.ca",
        )
        db_session.add(integration)
        db_session.flush()

        # Construct ParentDigestSettings WITHOUT an explicit digest_format
        # so we exercise the model column default.
        settings_row = ParentDigestSettings(integration_id=integration.id)
        db_session.add(settings_row)
        db_session.commit()
        db_session.refresh(settings_row)

        assert settings_row.digest_format == "sectioned"

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
# Manual Sync
# ---------------------------------------------------------------------------


class TestManualSync:
    @patch(
        "app.services.parent_gmail_service.fetch_child_emails",
        return_value={"emails": [], "synced_at": None},
    )
    def test_sync_returns_count_not_emails(self, mock_fetch, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(f"{PREFIX}/integrations/{iid}/sync", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "email_count" in data
        assert "message" in data
        assert "emails" not in data  # Must not leak raw email content


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

    def test_integration_response_has_monitored_emails(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.get(f"{PREFIX}/integrations/{iid}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "monitored_emails" in data
        assert isinstance(data["monitored_emails"], list)


# ---------------------------------------------------------------------------
# Monitored Emails CRUD (#3178)
# ---------------------------------------------------------------------------

SECOND_PARENT_EMAIL = "digest_parent2@test.com"


class TestAddMonitoredEmail:
    def test_add_monitored_email(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"email_address": "teacher@school.ca", "label": "Math Teacher"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email_address"] == "teacher@school.ca"
        assert data["label"] == "Math Teacher"
        assert data["integration_id"] == iid

    def test_add_monitored_email_no_label(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"email_address": "office@school.ca"},
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["label"] is None


class TestListMonitoredEmails:
    def test_list_monitored_emails(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        # Add one first
        client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"email_address": "list_test@school.ca"},
            headers=headers,
        )
        resp = client.get(f"{PREFIX}/integrations/{iid}/monitored-emails", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(e["email_address"] == "list_test@school.ca" for e in data)


class TestRemoveMonitoredEmail:
    def test_remove_monitored_email(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        add_resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"email_address": "remove_test@school.ca"},
            headers=headers,
        )
        email_id = add_resp.json()["id"]
        resp = client.delete(
            f"{PREFIX}/integrations/{iid}/monitored-emails/{email_id}",
            headers=headers,
        )
        assert resp.status_code == 204

    def test_remove_nonexistent_monitored_email(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.delete(
            f"{PREFIX}/integrations/{iid}/monitored-emails/99999",
            headers=headers,
        )
        assert resp.status_code == 404


class TestAddDuplicateMonitoredEmail:
    def test_add_duplicate_monitored_email(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"email_address": "dup_test@school.ca"},
            headers=headers,
        )
        resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"email_address": "dup_test@school.ca"},
            headers=headers,
        )
        assert resp.status_code == 409


class TestMonitoredEmailLimit:
    def test_add_monitored_email_limit(self, client, db_session, setup):
        """Add 10 monitored emails then verify 11th is rejected."""
        from app.models.parent_gmail_integration import ParentDigestMonitoredEmail

        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id

        # Clear existing monitored emails for this integration
        db_session.query(ParentDigestMonitoredEmail).filter(
            ParentDigestMonitoredEmail.integration_id == iid,
        ).delete()
        db_session.commit()

        # Add 10 emails directly
        for i in range(10):
            me = ParentDigestMonitoredEmail(
                integration_id=iid,
                email_address=f"limit{i}@school.ca",
            )
            db_session.add(me)
        db_session.commit()

        # 11th should fail
        resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"email_address": "limit_overflow@school.ca"},
            headers=headers,
        )
        assert resp.status_code == 400
        assert "Maximum" in resp.json()["detail"]


class TestMonitoredEmailWrongUser:
    def test_monitored_email_wrong_user(self, client, db_session, setup):
        """Verify a different parent cannot access another parent's monitored emails."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        # Create a second parent
        parent2 = db_session.query(User).filter(User.email == SECOND_PARENT_EMAIL).first()
        if not parent2:
            parent2 = User(
                email=SECOND_PARENT_EMAIL,
                full_name="Digest Parent 2",
                role=UserRole.PARENT,
                hashed_password=get_password_hash(PASSWORD),
            )
            db_session.add(parent2)
            db_session.commit()

        headers2 = _auth(client, SECOND_PARENT_EMAIL)
        iid = setup["integration"].id

        # Try to list monitored emails of first parent's integration
        resp = client.get(f"{PREFIX}/integrations/{iid}/monitored-emails", headers=headers2)
        assert resp.status_code == 404

        # Try to add monitored email to first parent's integration
        resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"email_address": "hack@school.ca"},
            headers=headers2,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# From-name filter (#3652)
# ---------------------------------------------------------------------------


class TestSenderNameFilter:
    """#3652 — allow monitored senders to be filtered by From name."""

    @pytest.fixture(autouse=True)
    def _clear_monitored(self, db_session, setup):
        """Each test starts from a clean monitored_emails slate."""
        from app.models.parent_gmail_integration import ParentDigestMonitoredEmail
        iid = setup["integration"].id
        db_session.query(ParentDigestMonitoredEmail).filter(
            ParentDigestMonitoredEmail.integration_id == iid,
        ).delete()
        db_session.commit()

    def test_add_sender_name_only(self, client, setup):
        """A sender-name-only entry is accepted (no email_address)."""
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"sender_name": "Mrs. Smith", "label": "Math Teacher"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["sender_name"] == "Mrs. Smith"
        assert data["email_address"] is None
        assert data["label"] == "Math Teacher"

    def test_add_email_only_backward_compat(self, client, setup):
        """Email-only entry (no sender_name) still works — backward compat."""
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"email_address": "legacy@school.ca"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["email_address"] == "legacy@school.ca"
        assert data["sender_name"] is None

    def test_add_email_and_sender_name(self, client, setup):
        """Adding both email and sender_name works."""
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={
                "email_address": "principal@school.ca",
                "sender_name": "Principal Jones",
                "label": "Principal",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["email_address"] == "principal@school.ca"
        assert data["sender_name"] == "Principal Jones"

    def test_reject_empty_entry(self, client, setup):
        """Both email and sender_name empty is rejected."""
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"label": "empty only"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_reject_both_blank_strings(self, client, setup):
        """Whitespace-only strings for both email and sender_name is rejected."""
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"email_address": "  ", "sender_name": "  "},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_duplicate_detection_on_email_and_name(self, client, setup):
        """Duplicate with same email AND same sender_name returns 409."""
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        payload = {"email_address": "dup_combo@school.ca", "sender_name": "Dup Name"}
        r1 = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json=payload,
            headers=headers,
        )
        assert r1.status_code == 201
        r2 = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json=payload,
            headers=headers,
        )
        assert r2.status_code == 409

    def test_response_includes_sender_name_field(self, client, setup):
        """List responses include the sender_name field."""
        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"sender_name": "Name Only Sender"},
            headers=headers,
        )
        resp = client.get(f"{PREFIX}/integrations/{iid}/monitored-emails", headers=headers)
        assert resp.status_code == 200
        assert any(
            me.get("sender_name") == "Name Only Sender" and me.get("email_address") is None
            for me in resp.json()
        )


# ---------------------------------------------------------------------------
# Email Digest Dashboard (CB-EDIGEST-002 E1, #4589)
# ---------------------------------------------------------------------------


DASHBOARD_PARENT_EMAIL = "dashboard_parent@test.com"
DASHBOARD_TEACHER_EMAIL = "dashboard_teacher@test.com"


def _make_dashboard_parent(db_session):
    """Create a dedicated parent + teacher for dashboard tests.

    Isolated from the shared `setup` fixture so empty-state tests can drive
    the no_kids / paused / first_run conditions independently of the other
    suite data.
    """
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    parent = (
        db_session.query(User).filter(User.email == DASHBOARD_PARENT_EMAIL).first()
    )
    if parent is None:
        hashed = get_password_hash(PASSWORD)
        parent = User(
            email=DASHBOARD_PARENT_EMAIL,
            full_name="Dashboard Parent",
            role=UserRole.PARENT,
            hashed_password=hashed,
        )
        db_session.add(parent)
        db_session.commit()
        db_session.refresh(parent)

    teacher = (
        db_session.query(User).filter(User.email == DASHBOARD_TEACHER_EMAIL).first()
    )
    if teacher is None:
        hashed = get_password_hash(PASSWORD)
        teacher = User(
            email=DASHBOARD_TEACHER_EMAIL,
            full_name="Dashboard Teacher",
            role=UserRole.TEACHER,
            hashed_password=hashed,
        )
        db_session.add(teacher)
        db_session.commit()
        db_session.refresh(teacher)

    return parent, teacher


def _make_kid(db_session, parent, first_name, email):
    """Create a Student User + ParentChildProfile bound to `parent`."""
    from app.core.security import get_password_hash
    from app.models.parent_gmail_integration import ParentChildProfile
    from app.models.user import User, UserRole

    kid_user = db_session.query(User).filter(User.email == email).first()
    if kid_user is None:
        kid_user = User(
            email=email,
            full_name=first_name,
            role=UserRole.STUDENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(kid_user)
        db_session.commit()
        db_session.refresh(kid_user)

    profile = (
        db_session.query(ParentChildProfile)
        .filter(
            ParentChildProfile.parent_id == parent.id,
            ParentChildProfile.student_id == kid_user.id,
        )
        .first()
    )
    if profile is None:
        profile = ParentChildProfile(
            parent_id=parent.id,
            student_id=kid_user.id,
            first_name=first_name,
        )
        db_session.add(profile)
        db_session.commit()
        db_session.refresh(profile)
    return kid_user, profile


def _add_task(
    db_session,
    *,
    creator,
    assignee,
    title,
    due_date,
    source_message_id=None,
):
    """Insert a Task assigned to `assignee` with the given due_date."""
    from app.models.task import Task

    task = Task(
        created_by_user_id=creator.id,
        assigned_to_user_id=assignee.id,
        title=title,
        due_date=due_date,
        priority="medium",
        is_completed=False,
        source="email_digest",
        source_message_id=source_message_id,
    )
    db_session.add(task)
    db_session.commit()
    db_session.refresh(task)
    return task


def _purge_dashboard_state(db_session, parent_id):
    """Reset all CB-EDIGEST-002 inputs for `parent_id`.

    Called at the top of every dashboard test so tests can run in any order
    under the session-scoped DB fixture without inheriting tasks / profiles
    / integrations / logs from sibling tests.
    """
    from app.models.parent_gmail_integration import (
        DigestDeliveryLog,
        ParentChildProfile,
        ParentGmailIntegration,
    )
    from app.models.task import Task

    profiles = (
        db_session.query(ParentChildProfile)
        .filter(ParentChildProfile.parent_id == parent_id)
        .all()
    )
    student_ids = [p.student_id for p in profiles if p.student_id is not None]
    if student_ids:
        db_session.query(Task).filter(
            Task.assigned_to_user_id.in_(student_ids)
        ).delete(synchronize_session=False)

    db_session.query(ParentChildProfile).filter(
        ParentChildProfile.parent_id == parent_id
    ).delete(synchronize_session=False)
    db_session.query(DigestDeliveryLog).filter(
        DigestDeliveryLog.parent_id == parent_id
    ).delete(synchronize_session=False)
    db_session.query(ParentGmailIntegration).filter(
        ParentGmailIntegration.parent_id == parent_id
    ).delete(synchronize_session=False)
    db_session.commit()


class TestDashboard:
    """GET /api/parent/email-digest/dashboard — CB-EDIGEST-002 E1 (#4589)."""

    def test_dashboard_no_kids(self, client, db_session):
        parent, _teacher = _make_dashboard_parent(db_session)
        _purge_dashboard_state(db_session, parent.id)

        headers = _auth(client, DASHBOARD_PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/dashboard", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["empty_state"] == "no_kids"
        assert data["kids"] == []
        assert data["last_digest_at"] is None
        assert data["refreshed_at"] is not None

    def test_dashboard_all_paused(self, client, db_session):
        from app.models.parent_gmail_integration import (
            ParentDigestSettings,
            ParentGmailIntegration,
        )

        parent, _teacher = _make_dashboard_parent(db_session)
        _purge_dashboard_state(db_session, parent.id)
        _make_kid(db_session, parent, "Avery", "dashboard_kid_avery@test.com")

        # Two integrations: one inactive, one paused into the future.
        integ_a = ParentGmailIntegration(
            parent_id=parent.id,
            gmail_address="paused_a@gmail.com",
            google_id="gid_a",
            access_token="t",
            refresh_token="r",
            is_active=False,
        )
        integ_b = ParentGmailIntegration(
            parent_id=parent.id,
            gmail_address="paused_b@gmail.com",
            google_id="gid_b",
            access_token="t",
            refresh_token="r",
            is_active=True,
            paused_until=datetime.now(timezone.utc) + timedelta(days=14),
        )
        db_session.add_all([integ_a, integ_b])
        db_session.flush()
        db_session.add(ParentDigestSettings(integration_id=integ_a.id))
        db_session.add(ParentDigestSettings(integration_id=integ_b.id))
        db_session.commit()

        headers = _auth(client, DASHBOARD_PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/dashboard", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["empty_state"] == "paused"

    def test_dashboard_first_run(self, client, db_session):
        from app.models.parent_gmail_integration import (
            ParentDigestSettings,
            ParentGmailIntegration,
        )

        parent, _teacher = _make_dashboard_parent(db_session)
        _purge_dashboard_state(db_session, parent.id)
        _make_kid(db_session, parent, "Riley", "dashboard_kid_riley@test.com")

        # Active integration, no DigestDeliveryLog row yet.
        integ = ParentGmailIntegration(
            parent_id=parent.id,
            gmail_address="firstrun@gmail.com",
            google_id="gid_fr",
            access_token="t",
            refresh_token="r",
            is_active=True,
        )
        db_session.add(integ)
        db_session.flush()
        db_session.add(ParentDigestSettings(integration_id=integ.id))
        db_session.commit()

        headers = _auth(client, DASHBOARD_PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/dashboard", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["empty_state"] == "first_run"
        assert data["last_digest_at"] is None

    def test_dashboard_all_clear(self, client, db_session):
        from app.models.parent_gmail_integration import (
            DigestDeliveryLog,
            ParentDigestSettings,
            ParentGmailIntegration,
        )

        parent, _teacher = _make_dashboard_parent(db_session)
        _purge_dashboard_state(db_session, parent.id)
        _make_kid(db_session, parent, "Sky", "dashboard_kid_sky@test.com")

        integ = ParentGmailIntegration(
            parent_id=parent.id,
            gmail_address="calm@gmail.com",
            google_id="gid_calm",
            access_token="t",
            refresh_token="r",
            is_active=True,
        )
        db_session.add(integ)
        db_session.flush()
        db_session.add(ParentDigestSettings(integration_id=integ.id))
        db_session.add(
            DigestDeliveryLog(
                parent_id=parent.id,
                integration_id=integ.id,
                email_count=2,
                digest_content="Calm digest",
                channels_used="in_app,email",
                status="delivered",
            )
        )
        db_session.commit()

        headers = _auth(client, DASHBOARD_PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/dashboard", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["empty_state"] == "calm"
        assert len(data["kids"]) == 1
        assert data["kids"][0]["all_clear"] is True
        assert data["kids"][0]["urgent_items"] == []
        assert data["last_digest_at"] is not None

    def test_dashboard_normal_multi_kid(self, client, db_session):
        """Multi-kid normal path: empty_state=null + ordering by urgent count."""
        from app.models.parent_gmail_integration import (
            DigestDeliveryLog,
            ParentDigestSettings,
            ParentGmailIntegration,
        )

        parent, teacher = _make_dashboard_parent(db_session)
        _purge_dashboard_state(db_session, parent.id)
        kid_a_user, profile_a = _make_kid(
            db_session, parent, "Alice", "dashboard_kid_alice@test.com"
        )
        kid_b_user, profile_b = _make_kid(
            db_session, parent, "Bobby", "dashboard_kid_bobby@test.com"
        )

        integ = ParentGmailIntegration(
            parent_id=parent.id,
            gmail_address="multi@gmail.com",
            google_id="gid_multi",
            access_token="t",
            refresh_token="r",
            is_active=True,
        )
        db_session.add(integ)
        db_session.flush()
        db_session.add(ParentDigestSettings(integration_id=integ.id))
        db_session.add(
            DigestDeliveryLog(
                parent_id=parent.id,
                integration_id=integ.id,
                email_count=3,
                channels_used="in_app",
                status="delivered",
            )
        )
        db_session.commit()

        now = datetime.now(timezone.utc)
        # Bobby gets 2 urgent items today; Alice gets 1 urgent today + 1 in
        # 3 days (week-only). The multi-kid section ordering should put
        # Bobby first (more urgent items).
        _add_task(
            db_session,
            creator=teacher,
            assignee=kid_a_user,
            title="Alice — read chapter 3",
            due_date=now + timedelta(hours=4),
            source_message_id="msg-a-1",
        )
        _add_task(
            db_session,
            creator=teacher,
            assignee=kid_a_user,
            title="Alice — book report",
            due_date=now + timedelta(days=3),
            source_message_id="msg-a-2",
        )
        _add_task(
            db_session,
            creator=teacher,
            assignee=kid_b_user,
            title="Bobby — math worksheet",
            due_date=now + timedelta(hours=2),
            source_message_id="msg-b-1",
        )
        _add_task(
            db_session,
            creator=teacher,
            assignee=kid_b_user,
            title="Bobby — overdue spelling",
            due_date=now - timedelta(hours=6),
            source_message_id="msg-b-2",
        )

        headers = _auth(client, DASHBOARD_PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/dashboard", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["empty_state"] is None
        assert len(data["kids"]) == 2
        # PRD §F6 — kid with most urgent items first.
        assert data["kids"][0]["first_name"] == "Bobby"
        assert data["kids"][1]["first_name"] == "Alice"

        bobby = data["kids"][0]
        alice = data["kids"][1]
        assert len(bobby["urgent_items"]) == 2
        assert bobby["all_clear"] is False
        assert all(item["source_email_id"] for item in bobby["urgent_items"])

        assert len(alice["urgent_items"]) == 1
        # Alice has 1 urgent (today) + 1 future weekly task → 2 weekly buckets.
        assert len(alice["weekly_deadlines"]) >= 1
        assert all("day" in d and "items" in d for d in alice["weekly_deadlines"])

    def test_dashboard_tie_break_preserves_creation_order(self, client, db_session):
        """Pass-1 review I3 + pass-2 mutation hardening: when two kids have
        equal urgent counts, the secondary order MUST be
        ParentChildProfile.created_at ASC.

        Names chosen so creation order (Zara → Aiden) is the OPPOSITE of
        alphabetical order — distinguishes the stable creation-order
        contract from an accidental swap to alphabetical sort. The
        implementation relies on Python's stable list.sort + the primary
        `ORDER BY created_at ASC` from the profile query.
        """
        from app.models.parent_gmail_integration import (
            DigestDeliveryLog,
            ParentDigestSettings,
            ParentGmailIntegration,
        )

        parent, teacher = _make_dashboard_parent(db_session)
        _purge_dashboard_state(db_session, parent.id)

        # Profile creation order: Zara first, then Aiden. Both get exactly
        # 1 urgent task each → tie-break by creation order, NOT
        # alphabetical (which would put Aiden first).
        kid_c_user, _ = _make_kid(
            db_session, parent, "Zara", "dashboard_kid_zara@test.com"
        )
        kid_d_user, _ = _make_kid(
            db_session, parent, "Aiden", "dashboard_kid_aiden@test.com"
        )

        integ = ParentGmailIntegration(
            parent_id=parent.id,
            gmail_address="tiebreak@gmail.com",
            google_id="gid_tb",
            access_token="t",
            refresh_token="r",
            is_active=True,
        )
        db_session.add(integ)
        db_session.flush()
        db_session.add(ParentDigestSettings(integration_id=integ.id))
        db_session.add(
            DigestDeliveryLog(
                parent_id=parent.id,
                integration_id=integ.id,
                email_count=1,
                channels_used="in_app",
                status="delivered",
            )
        )
        db_session.commit()

        now = datetime.now(timezone.utc)
        _add_task(
            db_session,
            creator=teacher,
            assignee=kid_c_user,
            title="Zara — task A",
            due_date=now + timedelta(hours=2),
        )
        _add_task(
            db_session,
            creator=teacher,
            assignee=kid_d_user,
            title="Aiden — task A",
            due_date=now + timedelta(hours=2),
        )

        headers = _auth(client, DASHBOARD_PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/dashboard", headers=headers)
        assert resp.status_code == 200, resp.text
        kids = resp.json()["kids"]
        # Zara was created first → must come first under stable
        # tie-break, even though "Aiden" sorts alphabetically before "Zara".
        assert [k["first_name"] for k in kids] == ["Zara", "Aiden"]
        assert all(len(k["urgent_items"]) == 1 for k in kids)

    def test_dashboard_rbac_403(self, client, db_session):
        """Non-parent role gets 403 from require_role(PARENT)."""
        # Use the existing teacher seed from the shared `setup` fixture's pool.
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        non_parent_email = "dashboard_non_parent@test.com"
        existing = (
            db_session.query(User).filter(User.email == non_parent_email).first()
        )
        if existing is None:
            db_session.add(
                User(
                    email=non_parent_email,
                    full_name="Dashboard Student",
                    role=UserRole.STUDENT,
                    hashed_password=get_password_hash(PASSWORD),
                )
            )
            db_session.commit()

        headers = _auth(client, non_parent_email)
        resp = client.get(f"{PREFIX}/dashboard", headers=headers)
        assert resp.status_code == 403

    def test_dashboard_since_validation_rejects_unknown(self, client, db_session):
        """Pass-1 review I4: `since` is a Literal["today"]; unknown values
        must return 422 rather than being silently accepted."""
        parent, _teacher = _make_dashboard_parent(db_session)
        _purge_dashboard_state(db_session, parent.id)

        headers = _auth(client, DASHBOARD_PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/dashboard?since=tomorrow", headers=headers)
        assert resp.status_code == 422, resp.text

    def test_dashboard_rate_limit_60(self, client, db_session, app):
        """61st call within the same minute trips the 60/min limiter."""
        parent, _teacher = _make_dashboard_parent(db_session)
        _purge_dashboard_state(db_session, parent.id)

        headers = _auth(client, DASHBOARD_PARENT_EMAIL)
        app.state.limiter.enabled = True
        app.state.limiter.reset()
        try:
            for _ in range(60):
                resp = client.get(f"{PREFIX}/dashboard", headers=headers)
                assert resp.status_code == 200, resp.text
            resp = client.get(f"{PREFIX}/dashboard", headers=headers)
            assert resp.status_code == 429
        finally:
            app.state.limiter.enabled = False
            app.state.limiter.reset()
