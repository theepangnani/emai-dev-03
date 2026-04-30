"""Tests for CB-CMCP-001 M3-G 3G-3 — owner notification on cascade-flag (#4665).

Per locked decision D9=B + 3G-3 spec: when 3G-2's
:func:`apply_version_cascade` transitions an APPROVED ``study_guides``
row to PENDING_REVIEW because of a substantive SE change, we notify
the artifact's owner (teacher) via the existing CB-MCNI dev-03
notification service so the row appears in their review queue
without polling.

These tests mock the notification service entry point
(:func:`app.services.notification_service.send_multi_channel_notification`)
to verify call shape — they NEVER make a real notification API call
or insert real Notification rows beyond what the cascade itself
produces. The cascade audit + state transition are still exercised
end-to-end against the live SQLite test DB so we cover the
"notification fired ⇔ artifact transitioned" invariant.
"""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from conftest import PASSWORD


# ─────────────────────────────────────────────────────────────────────
# Fixtures (mirror tests/test_version_cascade.py)
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture()
def teacher_user(db_session):
    """Create a TEACHER user to own the cascaded study_guides under test.

    3G-3 spec frames the notification recipient as the artifact's
    teacher-owner. The cascade service itself reads the owner via
    ``study_guides.user_id`` — that column is the FK to ``users.id``
    regardless of role — but we use a TEACHER here to mirror the
    real-world cascade target.
    """
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = f"cascade_teacher_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="Cascade Teacher",
        role=UserRole.TEACHER,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_study_guide(
    db_session,
    *,
    user_id: int,
    se_codes: list[str] | None,
    state: str,
    title: str | None = None,
):
    """Insert a StudyGuide row with the supplied state + se_codes + title."""
    from app.models.study_guide import StudyGuide

    sg = StudyGuide(
        user_id=user_id,
        title=title or f"Cascade Notify {uuid4().hex[:6]}",
        content="# placeholder content",
        guide_type="study_guide",
        version=1,
        relationship_type="version",
        state=state,
        se_codes=se_codes,
    )
    db_session.add(sg)
    db_session.commit()
    db_session.refresh(sg)
    return sg


def _se(*, cb_code: str, parent_oe_id: int = 42) -> dict:
    return {
        "expectation_text": "describe the water cycle and its key processes",
        "cb_code": cb_code,
        "parent_oe_id": parent_oe_id,
    }


def _substantive_pair(
    *,
    cb_code: str,
    from_version: str = "2020-rev1",
    to_version: str = "2024",
) -> dict:
    """Build an SE pair that classifies as scope_substantive (parent_oe_id
    differs across versions; same cb_code on the SE rows themselves)."""
    return {
        "old_se": _se(cb_code=cb_code, parent_oe_id=42),
        "new_se": _se(cb_code=cb_code, parent_oe_id=99),
        "from_version": from_version,
        "to_version": to_version,
    }


def _wording_only_pair(*, cb_code: str) -> dict:
    """Build an SE pair that classifies as wording_only (identical SEs)."""
    return {
        "old_se": _se(cb_code=cb_code),
        "new_se": _se(cb_code=cb_code),
        "from_version": "2020-rev1",
        "to_version": "2024",
    }


# ─────────────────────────────────────────────────────────────────────
# Happy path — notification fires once per cascade-flagged artifact
# ─────────────────────────────────────────────────────────────────────


def test_cascade_sends_notification_to_artifact_owner(db_session, teacher_user):
    """Substantive cascade transitions APPROVED → PENDING_REVIEW AND
    sends one in-app notification to the artifact's owner with a
    ``/teacher/review/{artifact_id}`` link + cascade reason in body."""
    from app.models.notification import NotificationType
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import apply_version_cascade

    cb_code = f"CB-NOTIFY-{uuid4().hex[:6]}"
    sg = _make_study_guide(
        db_session,
        user_id=teacher_user.id,
        se_codes=[cb_code],
        state=ArtifactState.APPROVED,
        title="Grade 7 Water Cycle Study Guide",
    )

    with patch(
        "app.services.notification_service.send_multi_channel_notification"
    ) as mock_notify:
        result = apply_version_cascade(
            [
                _substantive_pair(
                    cb_code=cb_code,
                    from_version="2020-rev1",
                    to_version="2024",
                )
            ],
            db_session,
        )
        db_session.commit()
        db_session.refresh(sg)

    # 1. The cascade itself happened.
    assert sg.state == ArtifactState.PENDING_REVIEW
    assert sg.id in result.flagged_artifact_ids

    # 2. Exactly one notification call for the one flagged artifact.
    assert mock_notify.call_count == 1

    # 3. Call shape: recipient = owner, link = /teacher/review/{id},
    #    type = CMCP_CASCADE_FLAGGED, content carries cascade reason.
    _, kwargs = mock_notify.call_args
    assert kwargs["recipient"].id == teacher_user.id
    assert kwargs["sender"] is None  # system-driven cascade
    assert kwargs["notification_type"] == NotificationType.CMCP_CASCADE_FLAGGED
    assert kwargs["link"] == f"/teacher/review/{sg.id}"
    assert kwargs["channels"] == ["app_notification"]
    assert kwargs["source_type"] == "study_guide"
    assert kwargs["source_id"] == sg.id
    # Title preview + cb_code + version hop appear in the body so the
    # teacher knows WHY the artifact came back to the queue.
    assert "Grade 7 Water Cycle Study Guide" in kwargs["content"]
    assert cb_code in kwargs["content"]
    assert "2020-rev1" in kwargs["content"]
    assert "2024" in kwargs["content"]


def test_cascade_sends_one_notification_per_flagged_artifact(
    db_session, teacher_user
):
    """Two APPROVED artifacts referencing the same substantive SE → two
    notifications, one per flagged artifact."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import apply_version_cascade

    cb_code = f"CB-MULTI-NOTIFY-{uuid4().hex[:6]}"
    sg_a = _make_study_guide(
        db_session,
        user_id=teacher_user.id,
        se_codes=[cb_code],
        state=ArtifactState.APPROVED,
        title="Artifact A",
    )
    sg_b = _make_study_guide(
        db_session,
        user_id=teacher_user.id,
        se_codes=[cb_code, "CB-EXTRA"],
        state=ArtifactState.APPROVED,
        title="Artifact B",
    )

    with patch(
        "app.services.notification_service.send_multi_channel_notification"
    ) as mock_notify:
        apply_version_cascade(
            [_substantive_pair(cb_code=cb_code)],
            db_session,
        )
        db_session.commit()

    assert mock_notify.call_count == 2
    notified_ids = {
        call.kwargs["source_id"] for call in mock_notify.call_args_list
    }
    assert notified_ids == {sg_a.id, sg_b.id}


# ─────────────────────────────────────────────────────────────────────
# No-op cases — notification NOT sent
# ─────────────────────────────────────────────────────────────────────


def test_wording_only_cascade_does_not_send_notification(
    db_session, teacher_user
):
    """wording_only SE pair → no transition → no notification."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import apply_version_cascade

    cb_code = f"CB-WORDING-NOTIFY-{uuid4().hex[:6]}"
    sg = _make_study_guide(
        db_session,
        user_id=teacher_user.id,
        se_codes=[cb_code],
        state=ArtifactState.APPROVED,
    )

    with patch(
        "app.services.notification_service.send_multi_channel_notification"
    ) as mock_notify:
        apply_version_cascade(
            [_wording_only_pair(cb_code=cb_code)],
            db_session,
        )
        db_session.commit()
        db_session.refresh(sg)

    assert sg.state == ArtifactState.APPROVED
    mock_notify.assert_not_called()


def test_no_matching_artifact_does_not_send_notification(
    db_session, teacher_user
):
    """Substantive pair but no APPROVED artifact references the SE →
    no transition → no notification."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import apply_version_cascade

    target_cb = f"CB-NO-MATCH-{uuid4().hex[:6]}"
    other_cb = f"CB-OTHER-{uuid4().hex[:6]}"
    _make_study_guide(
        db_session,
        user_id=teacher_user.id,
        se_codes=[other_cb],
        state=ArtifactState.APPROVED,
    )

    with patch(
        "app.services.notification_service.send_multi_channel_notification"
    ) as mock_notify:
        apply_version_cascade(
            [_substantive_pair(cb_code=target_cb)],
            db_session,
        )
        db_session.commit()

    mock_notify.assert_not_called()


# ─────────────────────────────────────────────────────────────────────
# Edge cases — notification side-effect must not break the cascade
# ─────────────────────────────────────────────────────────────────────


def test_cascade_for_artifact_with_deleted_owner_does_not_crash(
    db_session, teacher_user, caplog, monkeypatch
):
    """If the artifact's owner User row is gone but the artifact is
    still present (e.g., the User row was soft-deleted, the FK
    constraint was relaxed, or any other shape where
    ``study_guides.user_id`` no longer resolves to a real user), the
    cascade still transitions the row + writes the audit, and the
    notification is skipped with a warn log. No crash.

    Implementation note: ``study_guides.user_id`` carries
    ``ON DELETE CASCADE`` in this schema, so we can't simulate the
    orphan by deleting the User row directly — that would cascade
    the study_guide too. Instead we patch the cascade module's User
    query so the recipient lookup returns ``None`` while leaving the
    row + FK in place. This isolates the "owner-not-found" branch.
    """
    import logging

    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import (
        CASCADE_AUDIT_ACTION,
        apply_version_cascade,
    )

    cb_code = f"CB-DELETED-OWNER-{uuid4().hex[:6]}"
    sg = _make_study_guide(
        db_session,
        user_id=teacher_user.id,
        se_codes=[cb_code],
        state=ArtifactState.APPROVED,
    )

    # Patch the User query inside the cascade's notification helper
    # so the owner lookup returns None — simulating a deleted /
    # orphaned owner without violating the live FK on this dialect.
    real_query = db_session.query

    def query_returning_no_user(model, *args, **kwargs):
        from app.models.user import User as _User
        result = real_query(model, *args, **kwargs)
        if model is _User:
            class _Empty:
                def filter(self, *a, **kw):  # noqa: D401, ARG002
                    return self

                def first(self):
                    return None

            return _Empty()
        return result

    monkeypatch.setattr(db_session, "query", query_returning_no_user)

    with caplog.at_level(logging.WARNING, logger="app.services.cmcp.version_cascade"):
        # Real notification service is reachable (we did not mock
        # send_multi_channel_notification) — the helper short-circuits
        # at the User lookup, so it never gets called. This verifies
        # the owner-not-found path warns + swallows without raising.
        result = apply_version_cascade(
            [_substantive_pair(cb_code=cb_code)],
            db_session,
        )
        db_session.commit()

    # Restore real query for assertion-side reads.
    monkeypatch.setattr(db_session, "query", real_query)
    db_session.refresh(sg)

    # Cascade transition + audit row still wrote.
    assert sg.state == ArtifactState.PENDING_REVIEW
    assert sg.id in result.flagged_artifact_ids
    from app.models.audit_log import AuditLog
    audit_rows = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == CASCADE_AUDIT_ACTION)
        .filter(AuditLog.resource_id == sg.id)
        .all()
    )
    assert len(audit_rows) == 1

    # And the warn-log fired.
    assert any(
        "cmcp.cascade.notify.skipped" in rec.message
        and "owner_not_found" in rec.message
        for rec in caplog.records
    )


def test_notification_failure_does_not_rollback_cascade(
    db_session, teacher_user
):
    """If send_multi_channel_notification raises, the cascade's state
    transition + audit row stay committed. The notification helper is
    best-effort and must never propagate."""
    from app.services.cmcp.artifact_state import ArtifactState
    from app.services.cmcp.version_cascade import (
        CASCADE_AUDIT_ACTION,
        apply_version_cascade,
    )

    cb_code = f"CB-NOTIFY-FAIL-{uuid4().hex[:6]}"
    sg = _make_study_guide(
        db_session,
        user_id=teacher_user.id,
        se_codes=[cb_code],
        state=ArtifactState.APPROVED,
    )

    with patch(
        "app.services.notification_service.send_multi_channel_notification",
        side_effect=RuntimeError("simulated send failure"),
    ) as mock_notify:
        result = apply_version_cascade(
            [_substantive_pair(cb_code=cb_code)],
            db_session,
        )
        db_session.commit()
        db_session.refresh(sg)

    # Notification was attempted exactly once for the one flagged row.
    assert mock_notify.call_count == 1

    # Cascade state transition committed despite the notification
    # exception — best-effort contract holds.
    assert sg.state == ArtifactState.PENDING_REVIEW
    assert sg.id in result.flagged_artifact_ids

    # Audit row still in place.
    from app.models.audit_log import AuditLog
    audit_rows = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == CASCADE_AUDIT_ACTION)
        .filter(AuditLog.resource_id == sg.id)
        .all()
    )
    assert len(audit_rows) == 1


def test_empty_diff_does_not_send_notification(db_session):
    """Empty version_diff → no work, no notification call."""
    from app.services.cmcp.version_cascade import apply_version_cascade

    with patch(
        "app.services.notification_service.send_multi_channel_notification"
    ) as mock_notify:
        result = apply_version_cascade([], db_session)

    assert result.flagged_artifact_ids == []
    mock_notify.assert_not_called()


# ─────────────────────────────────────────────────────────────────────
# Notification type contract
# ─────────────────────────────────────────────────────────────────────


def test_cmcp_cascade_flagged_notification_type_is_registered():
    """The notification type the cascade emits is registered on the
    NotificationType enum so the model + frontend filter logic stay
    in lockstep with the service's emit string."""
    from app.models.notification import NotificationType
    from app.services.cmcp.version_cascade import (
        CASCADE_NOTIFICATION_TYPE_VALUE,
    )

    assert NotificationType.CMCP_CASCADE_FLAGGED.value == CASCADE_NOTIFICATION_TYPE_VALUE
    assert CASCADE_NOTIFICATION_TYPE_VALUE == "cmcp.cascade.flagged"
