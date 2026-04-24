"""Tests for unified digest v2 parent-level monitored senders API (#4014).

Covers POST/GET/PATCH/DELETE on /api/parent/email-digest/monitored-senders,
plus dual-write from the legacy /monitored-emails endpoint into the new
parent_digest_monitored_senders + sender_child_assignments tables.
"""

import pytest
from conftest import PASSWORD, _auth


PARENT_EMAIL = "senders_parent@test.com"
OTHER_PARENT_EMAIL = "senders_other_parent@test.com"
STUDENT_EMAIL = "senders_student@test.com"

PREFIX = "/api/parent/email-digest"


@pytest.fixture()
def setup(db_session):
    """Create a parent with two child profiles and one legacy integration."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.parent_gmail_integration import (
        ParentGmailIntegration,
        ParentChildProfile,
        ParentDigestMonitoredSender,
        SenderChildAssignment,
    )

    parent = db_session.query(User).filter(User.email == PARENT_EMAIL).first()
    if not parent:
        parent = User(
            email=PARENT_EMAIL,
            full_name="Senders Parent",
            role=UserRole.PARENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(parent)
        db_session.commit()

    other = db_session.query(User).filter(User.email == OTHER_PARENT_EMAIL).first()
    if not other:
        other = User(
            email=OTHER_PARENT_EMAIL,
            full_name="Other Parent",
            role=UserRole.PARENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(other)
        db_session.commit()

    student = db_session.query(User).filter(User.email == STUDENT_EMAIL).first()
    if not student:
        student = User(
            email=STUDENT_EMAIL,
            full_name="Senders Student",
            role=UserRole.STUDENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(student)
        db_session.commit()

    # Clean slate — remove senders/profiles from any prior test run
    db_session.query(SenderChildAssignment).filter(
        SenderChildAssignment.sender_id.in_(
            db_session.query(ParentDigestMonitoredSender.id).filter(
                ParentDigestMonitoredSender.parent_id == parent.id,
            )
        )
    ).delete(synchronize_session=False)
    db_session.query(ParentDigestMonitoredSender).filter(
        ParentDigestMonitoredSender.parent_id == parent.id,
    ).delete()
    db_session.query(ParentChildProfile).filter(
        ParentChildProfile.parent_id == parent.id,
    ).delete()
    db_session.commit()

    profile_a = ParentChildProfile(parent_id=parent.id, first_name="Alex")
    profile_b = ParentChildProfile(parent_id=parent.id, first_name="Jordan")
    db_session.add_all([profile_a, profile_b])
    db_session.commit()

    # Legacy integration for dual-write scenarios
    integration = (
        db_session.query(ParentGmailIntegration)
        .filter(
            ParentGmailIntegration.parent_id == parent.id,
            ParentGmailIntegration.child_first_name == "Alex",
        )
        .first()
    )
    if not integration:
        integration = ParentGmailIntegration(
            parent_id=parent.id,
            gmail_address="senders_parent@gmail.com",
            google_id="google_senders",
            access_token="tok",
            refresh_token="tok",
            child_school_email="alex@school.ca",
            child_first_name="Alex",
        )
        db_session.add(integration)
        db_session.commit()

    return {
        "parent": parent,
        "other_parent": other,
        "student": student,
        "profile_a": profile_a,
        "profile_b": profile_b,
        "integration": integration,
    }


# ---------------------------------------------------------------------------
# POST /monitored-senders (create + dedupe-update)
# ---------------------------------------------------------------------------


class TestCreateSender:
    def test_create_sender_with_child_ids(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(
            f"{PREFIX}/monitored-senders",
            json={
                "email_address": "Teacher@School.ca",
                "sender_name": "Mrs. Smith",
                "label": "Math",
                "child_profile_ids": [setup["profile_a"].id],
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["email_address"] == "teacher@school.ca"  # lower-cased
        assert data["sender_name"] == "Mrs. Smith"
        assert data["label"] == "Math"
        assert data["applies_to_all"] is False
        assert data["child_profile_ids"] == [setup["profile_a"].id]

    def test_create_sender_with_all(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(
            f"{PREFIX}/monitored-senders",
            json={
                "email_address": "announce@school.ca",
                "child_profile_ids": "all",
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["applies_to_all"] is True
        assert data["child_profile_ids"] == []

    def test_create_sender_dedupes_on_email(self, client, setup):
        """Re-POSTing the same email updates assignments instead of erroring."""
        headers = _auth(client, PARENT_EMAIL)
        r1 = client.post(
            f"{PREFIX}/monitored-senders",
            json={
                "email_address": "dup@school.ca",
                "child_profile_ids": [setup["profile_a"].id],
            },
            headers=headers,
        )
        assert r1.status_code == 201
        sid = r1.json()["id"]

        r2 = client.post(
            f"{PREFIX}/monitored-senders",
            json={
                "email_address": "dup@school.ca",
                "child_profile_ids": [setup["profile_a"].id, setup["profile_b"].id],
            },
            headers=headers,
        )
        assert r2.status_code == 201
        assert r2.json()["id"] == sid  # same row
        assert set(r2.json()["child_profile_ids"]) == {
            setup["profile_a"].id,
            setup["profile_b"].id,
        }

    def test_create_sender_unknown_child_id(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(
            f"{PREFIX}/monitored-senders",
            json={
                "email_address": "x@y.ca",
                "child_profile_ids": [999999],
            },
            headers=headers,
        )
        assert resp.status_code == 404

    def test_create_sender_cannot_target_other_parents_child(self, client, db_session, setup):
        from app.models.parent_gmail_integration import ParentChildProfile

        other_profile = ParentChildProfile(
            parent_id=setup["other_parent"].id,
            first_name="OtherKid",
        )
        db_session.add(other_profile)
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(
            f"{PREFIX}/monitored-senders",
            json={
                "email_address": "cross@school.ca",
                "child_profile_ids": [other_profile.id],
            },
            headers=headers,
        )
        assert resp.status_code == 404

    def test_create_sender_invalid_email(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(
            f"{PREFIX}/monitored-senders",
            json={"email_address": "not-an-email", "child_profile_ids": "all"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_create_sender_unauthenticated(self, client, setup):
        resp = client.post(
            f"{PREFIX}/monitored-senders",
            json={"email_address": "x@y.ca", "child_profile_ids": "all"},
        )
        assert resp.status_code in (401, 403)

    def test_create_sender_wrong_role(self, client, setup):
        headers = _auth(client, STUDENT_EMAIL)
        resp = client.post(
            f"{PREFIX}/monitored-senders",
            json={"email_address": "x@y.ca", "child_profile_ids": "all"},
            headers=headers,
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /monitored-senders
# ---------------------------------------------------------------------------


class TestListSenders:
    def test_list_returns_own_senders(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        client.post(
            f"{PREFIX}/monitored-senders",
            json={"email_address": "a@s.ca", "child_profile_ids": [setup["profile_a"].id]},
            headers=headers,
        )
        client.post(
            f"{PREFIX}/monitored-senders",
            json={"email_address": "b@s.ca", "child_profile_ids": "all"},
            headers=headers,
        )
        resp = client.get(f"{PREFIX}/monitored-senders", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        emails = [s["email_address"] for s in data]
        assert "a@s.ca" in emails and "b@s.ca" in emails
        for s in data:
            assert "child_profile_ids" in s
            assert "applies_to_all" in s

    def test_list_does_not_leak_other_parents(self, client, db_session, setup):
        # Seed a sender for the other parent
        from app.models.parent_gmail_integration import ParentDigestMonitoredSender

        other_sender = ParentDigestMonitoredSender(
            parent_id=setup["other_parent"].id,
            email_address="leak@school.ca",
        )
        db_session.add(other_sender)
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/monitored-senders", headers=headers)
        assert resp.status_code == 200
        emails = [s["email_address"] for s in resp.json()]
        assert "leak@school.ca" not in emails

    def test_list_unauthenticated(self, client, setup):
        resp = client.get(f"{PREFIX}/monitored-senders")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# PATCH /monitored-senders/{id}/assignments
# ---------------------------------------------------------------------------


class TestPatchAssignments:
    def test_replace_assignments(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        r = client.post(
            f"{PREFIX}/monitored-senders",
            json={"email_address": "patch@s.ca", "child_profile_ids": [setup["profile_a"].id]},
            headers=headers,
        )
        sid = r.json()["id"]

        resp = client.patch(
            f"{PREFIX}/monitored-senders/{sid}/assignments",
            json={"child_profile_ids": [setup["profile_b"].id]},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["child_profile_ids"] == [setup["profile_b"].id]
        assert resp.json()["applies_to_all"] is False

    def test_replace_with_all(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        r = client.post(
            f"{PREFIX}/monitored-senders",
            json={"email_address": "patch2@s.ca", "child_profile_ids": [setup["profile_a"].id]},
            headers=headers,
        )
        sid = r.json()["id"]

        resp = client.patch(
            f"{PREFIX}/monitored-senders/{sid}/assignments",
            json={"child_profile_ids": "all"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["applies_to_all"] is True
        assert resp.json()["child_profile_ids"] == []

    def test_patch_from_all_back_to_explicit(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        r = client.post(
            f"{PREFIX}/monitored-senders",
            json={"email_address": "swap@s.ca", "child_profile_ids": "all"},
            headers=headers,
        )
        sid = r.json()["id"]

        resp = client.patch(
            f"{PREFIX}/monitored-senders/{sid}/assignments",
            json={"child_profile_ids": [setup["profile_a"].id]},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["applies_to_all"] is False
        assert resp.json()["child_profile_ids"] == [setup["profile_a"].id]

    def test_patch_nonexistent(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.patch(
            f"{PREFIX}/monitored-senders/999999/assignments",
            json={"child_profile_ids": "all"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_patch_other_parents_sender(self, client, db_session, setup):
        from app.models.parent_gmail_integration import ParentDigestMonitoredSender

        other_sender = ParentDigestMonitoredSender(
            parent_id=setup["other_parent"].id,
            email_address="other@s.ca",
        )
        db_session.add(other_sender)
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.patch(
            f"{PREFIX}/monitored-senders/{other_sender.id}/assignments",
            json={"child_profile_ids": "all"},
            headers=headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /monitored-senders/{id}
# ---------------------------------------------------------------------------


class TestDeleteSender:
    def test_delete_own_sender(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        r = client.post(
            f"{PREFIX}/monitored-senders",
            json={"email_address": "del@s.ca", "child_profile_ids": "all"},
            headers=headers,
        )
        sid = r.json()["id"]
        resp = client.delete(f"{PREFIX}/monitored-senders/{sid}", headers=headers)
        assert resp.status_code == 204

        # Gone from list
        lst = client.get(f"{PREFIX}/monitored-senders", headers=headers).json()
        assert all(s["id"] != sid for s in lst)

    def test_delete_nonexistent(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.delete(f"{PREFIX}/monitored-senders/999999", headers=headers)
        assert resp.status_code == 404

    def test_delete_other_parents_sender(self, client, db_session, setup):
        from app.models.parent_gmail_integration import ParentDigestMonitoredSender

        other_sender = ParentDigestMonitoredSender(
            parent_id=setup["other_parent"].id,
            email_address="other_del@s.ca",
        )
        db_session.add(other_sender)
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.delete(
            f"{PREFIX}/monitored-senders/{other_sender.id}",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_delete_cascades_assignments(self, client, db_session, setup):
        from app.models.parent_gmail_integration import SenderChildAssignment

        headers = _auth(client, PARENT_EMAIL)
        r = client.post(
            f"{PREFIX}/monitored-senders",
            json={
                "email_address": "cascade@s.ca",
                "child_profile_ids": [setup["profile_a"].id, setup["profile_b"].id],
            },
            headers=headers,
        )
        sid = r.json()["id"]

        client.delete(f"{PREFIX}/monitored-senders/{sid}", headers=headers)

        remaining = (
            db_session.query(SenderChildAssignment)
            .filter(SenderChildAssignment.sender_id == sid)
            .count()
        )
        assert remaining == 0


# ---------------------------------------------------------------------------
# Dual-write: legacy /monitored-emails must mirror to v2 tables
# ---------------------------------------------------------------------------


class TestDualWrite:
    def test_legacy_write_creates_v2_sender(self, client, db_session, setup):
        from app.models.parent_gmail_integration import ParentDigestMonitoredSender

        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"email_address": "Legacy@School.ca", "sender_name": "Legacy Sender", "label": "legacy"},
            headers=headers,
        )
        assert resp.status_code == 201

        mirror = (
            db_session.query(ParentDigestMonitoredSender)
            .filter(
                ParentDigestMonitoredSender.parent_id == setup["parent"].id,
                ParentDigestMonitoredSender.email_address == "legacy@school.ca",
            )
            .first()
        )
        assert mirror is not None
        assert mirror.sender_name == "Legacy Sender"
        assert mirror.label == "legacy"

    def test_legacy_write_creates_v2_assignment_when_profile_matches(self, client, db_session, setup):
        from app.models.parent_gmail_integration import (
            ParentDigestMonitoredSender,
            SenderChildAssignment,
        )

        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        # integration.child_first_name == "Alex" → matches profile_a
        client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"email_address": "match@school.ca"},
            headers=headers,
        )

        sender = (
            db_session.query(ParentDigestMonitoredSender)
            .filter(
                ParentDigestMonitoredSender.parent_id == setup["parent"].id,
                ParentDigestMonitoredSender.email_address == "match@school.ca",
            )
            .one()
        )
        assignments = (
            db_session.query(SenderChildAssignment)
            .filter(SenderChildAssignment.sender_id == sender.id)
            .all()
        )
        assert len(assignments) == 1
        assert assignments[0].child_profile_id == setup["profile_a"].id

    def test_legacy_write_idempotent_on_v2_side(self, client, db_session, setup):
        """Re-POSTing the same email twice (after delete) must not duplicate v2 rows."""
        from app.models.parent_gmail_integration import (
            ParentDigestMonitoredSender,
            SenderChildAssignment,
        )

        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        payload = {"email_address": "idem@school.ca", "sender_name": "Idem"}
        r1 = client.post(f"{PREFIX}/integrations/{iid}/monitored-emails", json=payload, headers=headers)
        assert r1.status_code == 201

        # Delete legacy row and re-add — v2 sender must still be a single row.
        client.delete(
            f"{PREFIX}/integrations/{iid}/monitored-emails/{r1.json()['id']}",
            headers=headers,
        )
        r2 = client.post(f"{PREFIX}/integrations/{iid}/monitored-emails", json=payload, headers=headers)
        assert r2.status_code == 201

        senders = (
            db_session.query(ParentDigestMonitoredSender)
            .filter(
                ParentDigestMonitoredSender.parent_id == setup["parent"].id,
                ParentDigestMonitoredSender.email_address == "idem@school.ca",
            )
            .all()
        )
        assert len(senders) == 1

        assignments = (
            db_session.query(SenderChildAssignment)
            .filter(SenderChildAssignment.sender_id == senders[0].id)
            .all()
        )
        # Single assignment, not duplicated.
        assert len(assignments) == 1

    def test_legacy_write_skips_v2_when_no_email_address(self, client, db_session, setup):
        """Sender-name-only legacy entries don't trigger a v2 sender (v2 keys on email)."""
        from app.models.parent_gmail_integration import ParentDigestMonitoredSender

        headers = _auth(client, PARENT_EMAIL)
        iid = setup["integration"].id
        before = (
            db_session.query(ParentDigestMonitoredSender)
            .filter(ParentDigestMonitoredSender.parent_id == setup["parent"].id)
            .count()
        )
        resp = client.post(
            f"{PREFIX}/integrations/{iid}/monitored-emails",
            json={"sender_name": "Name Only"},
            headers=headers,
        )
        assert resp.status_code == 201

        after = (
            db_session.query(ParentDigestMonitoredSender)
            .filter(ParentDigestMonitoredSender.parent_id == setup["parent"].id)
            .count()
        )
        assert after == before


# ---------------------------------------------------------------------------
# N+1 regression (#4049) — list_monitored_senders eager-loads child_assignments
# ---------------------------------------------------------------------------


class TestListSendersQueryCount:
    def test_list_senders_is_constant_query_count(self, client, db_session, setup):
        """Seed 5 senders × 2 assignments per sender. The list endpoint must
        issue a constant number of SELECTs regardless of the N× factor."""
        from sqlalchemy import event
        from app.models.parent_gmail_integration import (
            ParentDigestMonitoredSender,
            SenderChildAssignment,
        )

        # Purge existing fixture senders for this parent.
        db_session.query(SenderChildAssignment).filter(
            SenderChildAssignment.sender_id.in_(
                db_session.query(ParentDigestMonitoredSender.id).filter(
                    ParentDigestMonitoredSender.parent_id == setup["parent"].id,
                )
            )
        ).delete(synchronize_session=False)
        db_session.query(ParentDigestMonitoredSender).filter(
            ParentDigestMonitoredSender.parent_id == setup["parent"].id,
        ).delete()
        db_session.commit()

        senders = []
        for i in range(5):
            s = ParentDigestMonitoredSender(
                parent_id=setup["parent"].id,
                email_address=f"teacher{i}@school.ca",
                sender_name=f"Teacher {i}",
            )
            db_session.add(s)
            senders.append(s)
        db_session.commit()
        for s in senders:
            for pid in (setup["profile_a"].id, setup["profile_b"].id):
                db_session.add(SenderChildAssignment(
                    sender_id=s.id,
                    child_profile_id=pid,
                ))
        db_session.commit()

        engine = db_session.bind
        select_count = {"n": 0}

        def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if statement.strip().lower().startswith("select"):
                select_count["n"] += 1

        event.listen(engine, "before_cursor_execute", _before_cursor_execute)
        try:
            headers = _auth(client, PARENT_EMAIL)
            resp = client.get(f"{PREFIX}/monitored-senders", headers=headers)
        finally:
            event.remove(engine, "before_cursor_execute", _before_cursor_execute)

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 5
        # Each sender should show both profile ids in its assignments
        for s in data:
            assert len(s["child_profile_ids"]) == 2

        assert select_count["n"] <= 10, (
            f"list_monitored_senders issued {select_count['n']} SELECTs for "
            f"5 senders × 2 assignments — likely N+1 on child_assignments."
        )


# ---------------------------------------------------------------------------
# SAVEPOINT resilience (#4050) — dual-write failure must NOT poison session
# ---------------------------------------------------------------------------


class TestDualWriteSavepointResilience:
    def test_dual_write_failure_does_not_poison_session(self, db_session):
        """If _dual_write_sender_v2 raises midway, the outer session must
        still be usable — the SAVEPOINT rolls back only the v2 inserts."""
        from app.api.routes.parent_email_digest import _dual_write_sender_v2
        from app.models.parent_gmail_integration import (
            ParentGmailIntegration,
            ParentDigestMonitoredSender,
        )
        from app.models.user import User, UserRole
        from app.core.security import get_password_hash

        parent = (
            db_session.query(User)
            .filter(User.email == "savepoint_parent@test.com")
            .first()
        )
        if not parent:
            parent = User(
                email="savepoint_parent@test.com",
                full_name="Savepoint Parent",
                role=UserRole.PARENT,
                hashed_password=get_password_hash(PASSWORD),
            )
            db_session.add(parent)
            db_session.commit()

        integration = ParentGmailIntegration(
            parent_id=parent.id,
            gmail_address="sp_parent@gmail.com",
            google_id="google_sp",
            access_token="tok",
            refresh_token="tok",
            child_school_email="kid@school.ca",
            child_first_name="Kid",
        )
        db_session.add(integration)
        db_session.commit()

        # Force a duplicate sender → second call inside SAVEPOINT will raise
        # IntegrityError on flush (unique parent_id+email constraint).
        existing = ParentDigestMonitoredSender(
            parent_id=parent.id,
            email_address="boom@school.ca",
            applies_to_all=False,
        )
        db_session.add(existing)
        db_session.commit()

        # Monkey-patch the sender query to return None so the dual-write
        # helper tries to INSERT a duplicate row — triggering the flush
        # inside the SAVEPOINT to fail.
        from unittest.mock import patch

        # Simpler: just invoke with an email that already exists but bypass
        # the existence check by mocking the first query to return None.
        orig_query = db_session.query

        call_state = {"first_sender_query": True}

        def fake_query(*args, **kwargs):
            q = orig_query(*args, **kwargs)
            if (
                call_state["first_sender_query"]
                and len(args) == 1
                and args[0] is ParentDigestMonitoredSender
            ):
                call_state["first_sender_query"] = False
                class _Wrapper:
                    def filter(self, *a, **kw):
                        class _Q:
                            def first(_self):
                                return None
                        return _Q()
                return _Wrapper()
            return q

        with patch.object(db_session, "query", side_effect=fake_query):
            # Should NOT raise — savepoint swallows the IntegrityError.
            _dual_write_sender_v2(
                db_session,
                parent_id=parent.id,
                integration=integration,
                email_address="boom@school.ca",
                sender_name="Boom",
                label=None,
            )

        # Session must still be usable — subsequent writes succeed.
        probe = ParentDigestMonitoredSender(
            parent_id=parent.id,
            email_address="post_failure@school.ca",
            applies_to_all=False,
        )
        db_session.add(probe)
        db_session.commit()  # Would fail with "transaction has been rolled back" if poisoned

        assert probe.id is not None


# ---------------------------------------------------------------------------
# MFIPPA (#4057) — dual-write exception log must not leak student addresses
# ---------------------------------------------------------------------------


class TestDualWritePIIScrub:
    def test_dual_write_failure_log_scrubs_raw_email(self, db_session, caplog, monkeypatch):
        """When _dual_write_sender_v2 raises inside the SAVEPOINT, the
        explicit exception log MESSAGE must NOT contain the raw email
        address. It must contain parent_id, integration_id, and a
        12-char SHA-256 hash prefix (for traceability).

        We force a generic RuntimeError on the inner query so the
        traceback itself does not carry SQL params that would leak
        the address; this test verifies the explicit log message, which
        is what the MFIPPA fix controls.
        """
        import hashlib
        import logging as _logging

        from app.api.routes import parent_email_digest as ped_module
        from app.api.routes.parent_email_digest import _dual_write_sender_v2
        from app.models.parent_gmail_integration import (
            ParentGmailIntegration,
        )
        from app.models.user import User, UserRole
        from app.core.security import get_password_hash

        parent = (
            db_session.query(User)
            .filter(User.email == "mfippa_dw_parent@test.com")
            .first()
        )
        if not parent:
            parent = User(
                email="mfippa_dw_parent@test.com",
                full_name="MFIPPA Parent",
                role=UserRole.PARENT,
                hashed_password=get_password_hash(PASSWORD),
            )
            db_session.add(parent)
            db_session.commit()

        integration = ParentGmailIntegration(
            parent_id=parent.id,
            gmail_address="mfippa_dw@gmail.com",
            google_id="google_mfippa_dw",
            access_token="tok",
            refresh_token="tok",
            child_school_email="kid@school.ca",
            child_first_name="Kid",
        )
        db_session.add(integration)
        db_session.commit()

        target_email = "thanushan.g@ocdsb.ca"

        # Force a generic RuntimeError inside the SAVEPOINT so the
        # traceback does not independently leak the email via SQL params.
        def _boom(*args, **kwargs):
            raise RuntimeError("forced dual-write failure")

        monkeypatch.setattr(db_session, "query", _boom)

        caplog.set_level(_logging.ERROR, logger=ped_module.logger.name)
        _dual_write_sender_v2(
            db_session,
            parent_id=parent.id,
            integration=integration,
            email_address=target_email,
            sender_name="Scrub Me",
            label=None,
        )

        # Inspect just the explicit log message (what the fix controls),
        # not the auto-appended traceback.
        messages = [rec.getMessage() for rec in caplog.records]
        assert messages, "expected at least one ERROR log record"
        msg = "\n".join(messages)

        expected_hash = hashlib.sha256(target_email.encode()).hexdigest()[:12]

        assert target_email not in msg, (
            f"Raw email leaked into exception log message: {msg!r}"
        )
        assert f"parent_id={parent.id}" in msg
        assert f"integration_id={integration.id}" in msg
        assert f"email_hash={expected_hash}" in msg
