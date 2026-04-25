"""Tests for CB-DCI-001 M0-11 — DCI consent (#4148)."""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi import HTTPException

from conftest import PASSWORD, _auth


# ── Fixtures ────────────────────────────────────────────────────


@pytest.fixture()
def parent_with_two_kids(db_session):
    """A parent linked to two kids — exercises per-kid distinct consent."""
    from app.core.security import get_password_hash
    from app.models.student import Student, RelationshipType, parent_students
    from app.models.user import User, UserRole

    suffix = uuid.uuid4().hex[:8]
    hashed = get_password_hash(PASSWORD)

    parent = User(
        email=f"dci-parent-{suffix}@test.com",
        full_name=f"DCI Parent {suffix}",
        role=UserRole.PARENT,
        roles="parent",
        hashed_password=hashed,
    )
    kid_user_a = User(
        email=f"dci-kid-a-{suffix}@test.com",
        full_name="Kid A",
        role=UserRole.STUDENT,
        roles="student",
        hashed_password=hashed,
    )
    kid_user_b = User(
        email=f"dci-kid-b-{suffix}@test.com",
        full_name="Kid B",
        role=UserRole.STUDENT,
        roles="student",
        hashed_password=hashed,
    )
    db_session.add_all([parent, kid_user_a, kid_user_b])
    db_session.commit()

    kid_a = Student(user_id=kid_user_a.id, grade_level=5)
    kid_b = Student(user_id=kid_user_b.id, grade_level=8)
    db_session.add_all([kid_a, kid_b])
    db_session.commit()

    db_session.execute(
        parent_students.insert().values(
            parent_id=parent.id,
            student_id=kid_a.id,
            relationship_type=RelationshipType.MOTHER,
        )
    )
    db_session.execute(
        parent_students.insert().values(
            parent_id=parent.id,
            student_id=kid_b.id,
            relationship_type=RelationshipType.MOTHER,
        )
    )
    db_session.commit()

    return {"parent": parent, "kid_a": kid_a, "kid_b": kid_b}


@pytest.fixture()
def other_parent(db_session):
    """An unrelated parent — exercises parent-isolation."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    suffix = uuid.uuid4().hex[:8]
    parent = User(
        email=f"dci-other-{suffix}@test.com",
        full_name=f"Other Parent {suffix}",
        role=UserRole.PARENT,
        roles="parent",
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(parent)
    db_session.commit()
    return parent


# ── GET /api/dci/consent/{kid_id} ───────────────────────────────


class TestGetConsent:
    def test_default_snapshot_returned_when_no_row(self, client, parent_with_two_kids):
        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, parent.email)

        resp = client.get(f"/api/dci/consent/{kid_a.id}", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["kid_id"] == kid_a.id
        assert body["parent_id"] == parent.id
        # Fail-closed defaults per Bill 194 / spec § 11
        assert body["photo_ok"] is False
        assert body["voice_ok"] is False
        assert body["ai_ok"] is False
        assert body["retention_days"] == 90
        assert body["dci_enabled"] is True
        assert body["muted"] is False
        assert body["kid_push_time"] == "15:15"
        assert body["parent_push_time"] == "19:00"
        assert body["allowed_retention_days"] == [90, 365, 1095]

    def test_404_when_kid_not_linked_to_parent(
        self, client, parent_with_two_kids, other_parent
    ):
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, other_parent.email)
        resp = client.get(f"/api/dci/consent/{kid_a.id}", headers=headers)
        assert resp.status_code == 404, resp.text

    def test_unauthenticated_rejected(self, client, parent_with_two_kids):
        kid_a = parent_with_two_kids["kid_a"]
        resp = client.get(f"/api/dci/consent/{kid_a.id}")
        assert resp.status_code in (401, 403)

    def test_list_returns_one_per_linked_kid(self, client, parent_with_two_kids):
        parent = parent_with_two_kids["parent"]
        headers = _auth(client, parent.email)
        resp = client.get("/api/dci/consent", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        kid_ids = sorted(item["kid_id"] for item in body["items"])
        assert kid_ids == sorted([
            parent_with_two_kids["kid_a"].id,
            parent_with_two_kids["kid_b"].id,
        ])


# ── POST /api/dci/consent ───────────────────────────────────────


class TestPostConsent:
    def test_consent_on_off_toggle(self, client, parent_with_two_kids):
        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, parent.email)

        # Toggle ON
        resp = client.post(
            "/api/dci/consent",
            headers=headers,
            json={"kid_id": kid_a.id, "photo_ok": True, "voice_ok": True, "ai_ok": True},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["photo_ok"] is True
        assert body["voice_ok"] is True
        assert body["ai_ok"] is True

        # Read back
        resp2 = client.get(f"/api/dci/consent/{kid_a.id}", headers=headers)
        assert resp2.status_code == 200
        assert resp2.json()["ai_ok"] is True

        # Toggle OFF (partial update — only ai_ok)
        resp3 = client.post(
            "/api/dci/consent",
            headers=headers,
            json={"kid_id": kid_a.id, "ai_ok": False},
        )
        assert resp3.status_code == 200
        body3 = resp3.json()
        assert body3["ai_ok"] is False
        # photo_ok / voice_ok preserved
        assert body3["photo_ok"] is True
        assert body3["voice_ok"] is True

    def test_retention_validation(self, client, parent_with_two_kids):
        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, parent.email)

        # Valid retentions
        for days in (90, 365, 1095):
            resp = client.post(
                "/api/dci/consent",
                headers=headers,
                json={"kid_id": kid_a.id, "retention_days": days},
            )
            assert resp.status_code == 200, f"days={days}: {resp.text}"
            assert resp.json()["retention_days"] == days

        # Invalid retention rejected
        resp = client.post(
            "/api/dci/consent",
            headers=headers,
            json={"kid_id": kid_a.id, "retention_days": 30},
        )
        assert resp.status_code == 400, resp.text

    def test_settings_fields_persist(self, client, parent_with_two_kids):
        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, parent.email)

        resp = client.post(
            "/api/dci/consent",
            headers=headers,
            json={
                "kid_id": kid_a.id,
                "dci_enabled": False,
                "muted": True,
                "kid_push_time": "16:30",
                "parent_push_time": "20:15",
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["dci_enabled"] is False
        assert body["muted"] is True
        assert body["kid_push_time"] == "16:30"
        assert body["parent_push_time"] == "20:15"

    def test_invalid_push_time_rejected(self, client, parent_with_two_kids):
        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, parent.email)

        for bad in ("3:15pm", "25:00", "10-30", "abcd"):
            resp = client.post(
                "/api/dci/consent",
                headers=headers,
                json={"kid_id": kid_a.id, "kid_push_time": bad},
            )
            assert resp.status_code == 400, f"bad={bad!r}: {resp.text}"

    def test_other_parent_cannot_post_for_unowned_kid(
        self, client, parent_with_two_kids, other_parent
    ):
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, other_parent.email)
        resp = client.post(
            "/api/dci/consent",
            headers=headers,
            json={"kid_id": kid_a.id, "ai_ok": True},
        )
        assert resp.status_code == 404, resp.text


# ── Multi-kid distinct consent ──────────────────────────────────


class TestMultiKidDistinctConsent:
    def test_per_kid_consent_isolated(self, client, parent_with_two_kids):
        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        kid_b = parent_with_two_kids["kid_b"]
        headers = _auth(client, parent.email)

        # Kid A: full consent
        client.post(
            "/api/dci/consent",
            headers=headers,
            json={
                "kid_id": kid_a.id,
                "photo_ok": True,
                "voice_ok": True,
                "ai_ok": True,
                "retention_days": 365,
            },
        )
        # Kid B: voice only
        client.post(
            "/api/dci/consent",
            headers=headers,
            json={
                "kid_id": kid_b.id,
                "photo_ok": False,
                "voice_ok": True,
                "ai_ok": False,
                "retention_days": 1095,
            },
        )

        resp_a = client.get(f"/api/dci/consent/{kid_a.id}", headers=headers).json()
        resp_b = client.get(f"/api/dci/consent/{kid_b.id}", headers=headers).json()

        assert resp_a["photo_ok"] is True and resp_a["ai_ok"] is True
        assert resp_a["retention_days"] == 365

        assert resp_b["photo_ok"] is False and resp_b["ai_ok"] is False
        assert resp_b["voice_ok"] is True
        assert resp_b["retention_days"] == 1095


# ── assert_dci_consent helper (M0-4 contract) ───────────────────


class TestAssertDciConsent:
    def test_403_consent_required_when_no_row(
        self, db_session, parent_with_two_kids
    ):
        from app.services.dci_consent_service import assert_dci_consent

        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        with pytest.raises(HTTPException) as exc:
            assert_dci_consent(db_session, kid_id=kid_a.id, parent_id=parent.id)
        assert exc.value.status_code == 403
        assert exc.value.detail == {"error": "consent_required"}

    def test_403_when_ai_ok_false(
        self, db_session, client, parent_with_two_kids
    ):
        from app.services.dci_consent_service import assert_dci_consent

        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, parent.email)
        # Photo + voice but not ai_ok
        client.post(
            "/api/dci/consent",
            headers=headers,
            json={"kid_id": kid_a.id, "photo_ok": True, "voice_ok": True, "ai_ok": False},
        )
        with pytest.raises(HTTPException) as exc:
            assert_dci_consent(db_session, kid_id=kid_a.id, parent_id=parent.id)
        assert exc.value.status_code == 403

    def test_403_when_dci_disabled(
        self, db_session, client, parent_with_two_kids
    ):
        from app.services.dci_consent_service import assert_dci_consent

        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, parent.email)
        client.post(
            "/api/dci/consent",
            headers=headers,
            json={"kid_id": kid_a.id, "ai_ok": True, "dci_enabled": False},
        )
        with pytest.raises(HTTPException) as exc:
            assert_dci_consent(db_session, kid_id=kid_a.id, parent_id=parent.id)
        assert exc.value.status_code == 403

    def test_403_when_modality_specific_consent_missing(
        self, db_session, client, parent_with_two_kids
    ):
        from app.services.dci_consent_service import assert_dci_consent

        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, parent.email)
        # ai_ok yes but photo_ok no
        client.post(
            "/api/dci/consent",
            headers=headers,
            json={"kid_id": kid_a.id, "ai_ok": True, "voice_ok": True, "photo_ok": False},
        )
        with pytest.raises(HTTPException) as exc:
            assert_dci_consent(
                db_session,
                kid_id=kid_a.id,
                parent_id=parent.id,
                requires_photo=True,
            )
        assert exc.value.status_code == 403

    def test_404_when_kid_not_owned_by_parent(
        self, db_session, parent_with_two_kids, other_parent
    ):
        from app.services.dci_consent_service import assert_dci_consent

        kid_a = parent_with_two_kids["kid_a"]
        # other_parent is unrelated to kid_a
        with pytest.raises(HTTPException) as exc:
            assert_dci_consent(
                db_session, kid_id=kid_a.id, parent_id=other_parent.id
            )
        assert exc.value.status_code == 404

    def test_passes_when_all_required_consent_granted(
        self, db_session, client, parent_with_two_kids
    ):
        from app.services.dci_consent_service import assert_dci_consent

        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, parent.email)
        client.post(
            "/api/dci/consent",
            headers=headers,
            json={
                "kid_id": kid_a.id,
                "ai_ok": True,
                "photo_ok": True,
                "voice_ok": True,
            },
        )
        snapshot = assert_dci_consent(
            db_session,
            kid_id=kid_a.id,
            parent_id=parent.id,
            requires_photo=True,
            requires_voice=True,
        )
        assert snapshot.ai_ok is True
        assert snapshot.photo_ok is True

    def test_single_query_round_trip(
        self, db_session, client, parent_with_two_kids
    ):
        """#4191: assert_dci_consent issues a single SELECT round-trip.

        Previously the helper ran 4 separate SELECTs (student, parent_students,
        checkin_consent, checkin_settings). The optimised version folds them
        into one inner+outer-join query.
        """
        from sqlalchemy import event

        from app.services.dci_consent_service import assert_dci_consent

        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, parent.email)
        client.post(
            "/api/dci/consent",
            headers=headers,
            json={
                "kid_id": kid_a.id,
                "ai_ok": True,
                "photo_ok": True,
                "voice_ok": True,
            },
        )

        # Count SELECT statements issued during the helper call.
        select_count = {"n": 0}
        engine = db_session.get_bind()

        def _on_execute(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                select_count["n"] += 1

        event.listen(engine, "before_cursor_execute", _on_execute)
        try:
            snapshot = assert_dci_consent(
                db_session,
                kid_id=kid_a.id,
                parent_id=parent.id,
                requires_photo=True,
                requires_voice=True,
            )
        finally:
            event.remove(engine, "before_cursor_execute", _on_execute)

        assert snapshot.ai_ok is True
        # Exactly one SELECT — the joined query. Allowing >1 would silently
        # let a regression slip back in.
        assert select_count["n"] == 1, (
            f"expected single-query round-trip, got {select_count['n']} SELECTs"
        )


# ── Audit log written on every consent change ───────────────────


class TestAuditLogOnConsentChange:
    def test_audit_entry_created_for_new_consent(
        self, client, db_session, parent_with_two_kids
    ):
        from app.models.audit_log import AuditLog

        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, parent.email)

        before_count = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "dci_consent_update")
            .count()
        )

        resp = client.post(
            "/api/dci/consent",
            headers=headers,
            json={"kid_id": kid_a.id, "ai_ok": True},
        )
        assert resp.status_code == 200, resp.text

        entries = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "dci_consent_update")
            .order_by(AuditLog.id.desc())
            .all()
        )
        assert len(entries) == before_count + 1
        latest = entries[0]
        assert latest.user_id == parent.id
        assert latest.resource_type == "checkin_consent"
        assert latest.resource_id == kid_a.id
        assert latest.details is not None
        details = json.loads(latest.details)
        assert details["consent_created"] is True
        assert details["after"]["ai_ok"] is True

    def test_audit_entry_records_field_diff_on_update(
        self, client, db_session, parent_with_two_kids
    ):
        from app.models.audit_log import AuditLog

        parent = parent_with_two_kids["parent"]
        kid_a = parent_with_two_kids["kid_a"]
        headers = _auth(client, parent.email)

        # First write — creates the row
        client.post(
            "/api/dci/consent",
            headers=headers,
            json={"kid_id": kid_a.id, "ai_ok": True, "photo_ok": True},
        )
        # Second write — should be 'created': False with before/after diff
        client.post(
            "/api/dci/consent",
            headers=headers,
            json={"kid_id": kid_a.id, "ai_ok": False},
        )

        entries = (
            db_session.query(AuditLog)
            .filter(
                AuditLog.action == "dci_consent_update",
                AuditLog.resource_id == kid_a.id,
            )
            .order_by(AuditLog.id.desc())
            .all()
        )
        # At least 2 entries (one per call)
        assert len(entries) >= 2
        latest = entries[0]
        details = json.loads(latest.details)
        assert details["consent_created"] is False
        assert details["before"]["ai_ok"] is True
        assert details["after"]["ai_ok"] is False
        # photo_ok preserved across the partial update
        assert details["before"]["photo_ok"] is True
        assert details["after"]["photo_ok"] is True
