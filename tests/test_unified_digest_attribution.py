"""Unit tests for the unified digest v2 attribution algorithm (#4012, #4015).

Covers:
- Header normalization (display names, case, multiple Delivered-To).
- Stage 1: school-email match (single kid, multi-kid, stamp
  forwarding_seen_at, parent scoping).
- Stage 2: monitored-sender fallback (specific assignments,
  applies_to_all).
- Stage 3: unattributed default.
- Sectioning helper (for_all_kids vs per_kid vs unattributed).
"""

from datetime import datetime, timezone

import pytest


def _models():
    """Lazy import — matches the conftest reload pattern."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.parent_gmail_integration import (
        ParentChildProfile,
        ParentChildSchoolEmail,
        ParentDigestMonitoredSender,
        ParentDiscoveredSchoolEmail,
        SenderChildAssignment,
    )
    return {
        "get_password_hash": get_password_hash,
        "User": User,
        "UserRole": UserRole,
        "ParentChildProfile": ParentChildProfile,
        "ParentChildSchoolEmail": ParentChildSchoolEmail,
        "ParentDigestMonitoredSender": ParentDigestMonitoredSender,
        "ParentDiscoveredSchoolEmail": ParentDiscoveredSchoolEmail,
        "SenderChildAssignment": SenderChildAssignment,
    }


def _make_parent(db, email):
    m = _models()
    existing = db.query(m["User"]).filter(m["User"].email == email).first()
    if existing:
        return existing
    p = m["User"](
        email=email,
        full_name="Attribution Parent",
        role=m["UserRole"].PARENT,
        hashed_password=m["get_password_hash"]("Password123!"),
    )
    db.add(p)
    db.commit()
    return p


def _make_profile(db, parent_id, first_name):
    m = _models()
    profile = m["ParentChildProfile"](parent_id=parent_id, first_name=first_name)
    db.add(profile)
    db.commit()
    return profile


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------


def test_extract_recipients_splits_commas_and_strips_display_names():
    from app.services.unified_digest_attribution import extract_recipient_addresses

    headers = {"To": '"Alex" <alex@school.ca>, BULK@school.ca'}
    got = extract_recipient_addresses(headers)
    assert got == ["alex@school.ca", "bulk@school.ca"]


def test_extract_recipients_merges_to_and_delivered_to_dedup():
    from app.services.unified_digest_attribution import extract_recipient_addresses

    headers = {
        "to": "alex@school.ca",
        "Delivered-To": ["parent+alex@gmail.com", "ALEX@school.ca"],
    }
    got = extract_recipient_addresses(headers)
    assert got == ["alex@school.ca", "parent+alex@gmail.com"]


def test_extract_recipients_empty_when_missing():
    from app.services.unified_digest_attribution import extract_recipient_addresses

    assert extract_recipient_addresses({}) == []
    assert extract_recipient_addresses({"To": ""}) == []


def test_extract_from_handles_display_name_and_case():
    from app.services.unified_digest_attribution import extract_from_address

    assert extract_from_address({"From": '"Teacher" <T@School.CA>'}) == "t@school.ca"
    assert extract_from_address({"from": "plain@x.com"}) == "plain@x.com"
    assert extract_from_address({}) == ""


# ---------------------------------------------------------------------------
# Stage 1: school-email match
# ---------------------------------------------------------------------------


def test_school_email_single_kid_match_stamps_forwarding_seen_at(db_session):
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_SCHOOL_EMAIL,
        attribute_email,
    )
    m = _models()

    parent = _make_parent(db_session, "school1@test.com")
    profile = _make_profile(db_session, parent.id, "Thanushan")
    school_email = m["ParentChildSchoolEmail"](
        child_profile_id=profile.id,
        email_address="thanushan@ocdsb.ca",
    )
    db_session.add(school_email)
    db_session.commit()

    assert school_email.forwarding_seen_at is None

    fixed = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    result = attribute_email(
        {"To": "thanushan@ocdsb.ca", "From": "noreply@example.com"},
        parent.id,
        db_session,
        now=fixed,
    )

    assert result == {"kid_ids": [profile.id], "source": ATTR_SOURCE_SCHOOL_EMAIL}

    db_session.refresh(school_email)
    # SQLite drops tzinfo on round-trip; compare naive wall-clock values.
    assert school_email.forwarding_seen_at.replace(tzinfo=None) == fixed.replace(tzinfo=None)


def test_school_email_multi_kid_match_returns_all_matched(db_session):
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_SCHOOL_EMAIL,
        attribute_email,
    )
    m = _models()

    parent = _make_parent(db_session, "school2@test.com")
    p1 = _make_profile(db_session, parent.id, "A")
    p2 = _make_profile(db_session, parent.id, "B")
    db_session.add_all([
        m["ParentChildSchoolEmail"](child_profile_id=p1.id, email_address="a@ocdsb.ca"),
        m["ParentChildSchoolEmail"](child_profile_id=p2.id, email_address="b@ocdsb.ca"),
    ])
    db_session.commit()

    result = attribute_email(
        {"To": "A@ocdsb.ca, b@ocdsb.ca"},
        parent.id,
        db_session,
    )
    assert result["source"] == ATTR_SOURCE_SCHOOL_EMAIL
    assert sorted(result["kid_ids"]) == sorted([p1.id, p2.id])


def test_school_email_does_not_leak_across_parents(db_session):
    """#4329 — parent_b has no registered school email AND no monitored
    sender, so the email falls to ``unattributed`` (it has a school-looking
    recipient, so it's NOT parent_direct). Critically: parent_a's school
    email row must not leak across the parent boundary."""
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_UNATTRIBUTED,
        attribute_email,
    )
    m = _models()

    parent_a = _make_parent(db_session, "isolation_a@test.com")
    parent_b = _make_parent(db_session, "isolation_b@test.com")
    prof_a = _make_profile(db_session, parent_a.id, "Akid")
    db_session.add(m["ParentChildSchoolEmail"](
        child_profile_id=prof_a.id,
        email_address="kid@gapps.yrdsb.ca",
    ))
    db_session.commit()

    # Parent B fetches an email addressed to Parent A's kid. Must not
    # match anything under Parent B's scope.
    result = attribute_email(
        {"To": "kid@gapps.yrdsb.ca"},
        parent_b.id,
        db_session,
    )
    assert result == {"kid_ids": [], "source": ATTR_SOURCE_UNATTRIBUTED}


# ---------------------------------------------------------------------------
# Stage 2: monitored-sender fallback
# ---------------------------------------------------------------------------


def test_sender_with_specific_assignments_downgrades_to_ambiguous(db_session):
    """#4329 — strict-subset sender match now downgrades to all-kids ambiguous
    when the recipient is a school-looking address that we can't tie back to
    a registered kid. The recipient pins the email as 'forwarded from school',
    but we can't be sure which kid this was actually for."""
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_SENDER_TAG_AMBIGUOUS,
        attribute_email,
    )
    m = _models()

    parent = _make_parent(db_session, "sender1@test.com")
    p1 = _make_profile(db_session, parent.id, "One")
    p2 = _make_profile(db_session, parent.id, "Two")
    p3 = _make_profile(db_session, parent.id, "Three")
    sender = m["ParentDigestMonitoredSender"](
        parent_id=parent.id,
        email_address="teacher@school.ca",
        applies_to_all=False,
    )
    db_session.add(sender)
    db_session.commit()
    db_session.add_all([
        m["SenderChildAssignment"](sender_id=sender.id, child_profile_id=p1.id),
        m["SenderChildAssignment"](sender_id=sender.id, child_profile_id=p2.id),
    ])
    db_session.commit()

    result = attribute_email(
        {
            "To": "unregistered.kid@gapps.yrdsb.ca",
            "From": "Teacher <TEACHER@school.ca>",
        },
        parent.id,
        db_session,
    )
    assert result["source"] == ATTR_SOURCE_SENDER_TAG_AMBIGUOUS
    assert sorted(result["kid_ids"]) == sorted([p1.id, p2.id, p3.id])


def test_sender_applies_to_all_returns_all_parent_profiles(db_session):
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_APPLIES_TO_ALL,
        attribute_email,
    )
    m = _models()

    parent = _make_parent(db_session, "sender_all@test.com")
    p1 = _make_profile(db_session, parent.id, "Alpha")
    p2 = _make_profile(db_session, parent.id, "Beta")
    p3 = _make_profile(db_session, parent.id, "Gamma")
    sender = m["ParentDigestMonitoredSender"](
        parent_id=parent.id,
        email_address="principal@school.ca",
        applies_to_all=True,
    )
    db_session.add(sender)
    db_session.commit()

    result = attribute_email(
        {
            "To": "broadcast@gapps.yrdsb.ca",
            "From": "principal@school.ca",
        },
        parent.id,
        db_session,
    )
    assert result["source"] == ATTR_SOURCE_APPLIES_TO_ALL
    assert sorted(result["kid_ids"]) == sorted([p1.id, p2.id, p3.id])


def test_sender_lookup_scoped_to_parent(db_session):
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_UNATTRIBUTED,
        attribute_email,
    )
    m = _models()

    parent_a = _make_parent(db_session, "scope_a@test.com")
    parent_b = _make_parent(db_session, "scope_b@test.com")
    prof_a = _make_profile(db_session, parent_a.id, "Kid")
    sender_a = m["ParentDigestMonitoredSender"](
        parent_id=parent_a.id,
        email_address="coach@school.ca",
    )
    db_session.add(sender_a)
    db_session.commit()
    db_session.add(m["SenderChildAssignment"](
        sender_id=sender_a.id,
        child_profile_id=prof_a.id,
    ))
    db_session.commit()

    # Parent B looking at the same From address should not attribute. Use an
    # unregistered school-looking recipient so we still exercise the Stage-3
    # sender lookup (else we'd short-circuit to parent_direct). #4329
    result = attribute_email(
        {
            "To": "stranger@gapps.yrdsb.ca",
            "From": "coach@school.ca",
        },
        parent_b.id,
        db_session,
    )
    assert result == {"kid_ids": [], "source": ATTR_SOURCE_UNATTRIBUTED}


# ---------------------------------------------------------------------------
# Stage 3: unattributed default
# ---------------------------------------------------------------------------


def test_no_recipient_no_sender_returns_parent_direct(db_session):
    """#4329 — when there are no school-looking recipients, the email
    didn't come through any school forwarding pipe. Surface as
    parent_direct rather than running sender-tag (which would mis-
    attribute when the parent's own correspondence happens to match
    a monitored sender)."""
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_PARENT_DIRECT,
        attribute_email,
    )
    parent = _make_parent(db_session, "un1@test.com")
    result = attribute_email({}, parent.id, db_session)
    assert result == {"kid_ids": [], "source": ATTR_SOURCE_PARENT_DIRECT}


def test_school_email_beats_sender_when_both_would_match(db_session):
    """When a recipient matches a school email AND the From matches a
    monitored sender, school-email wins (stage 1 short-circuits stage 2)."""
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_SCHOOL_EMAIL,
        attribute_email,
    )
    m = _models()

    parent = _make_parent(db_session, "priority@test.com")
    profile = _make_profile(db_session, parent.id, "Alpha")
    db_session.add(m["ParentChildSchoolEmail"](
        child_profile_id=profile.id,
        email_address="alpha@ocdsb.ca",
    ))
    # Also register the sender as applies_to_all — we still expect
    # school_email attribution because stage 1 matched first.
    sender = m["ParentDigestMonitoredSender"](
        parent_id=parent.id,
        email_address="teacher@school.ca",
        applies_to_all=True,
    )
    db_session.add(sender)
    db_session.commit()

    result = attribute_email(
        {"To": "alpha@ocdsb.ca", "From": "teacher@school.ca"},
        parent.id,
        db_session,
    )
    assert result["source"] == ATTR_SOURCE_SCHOOL_EMAIL
    assert result["kid_ids"] == [profile.id]


# ---------------------------------------------------------------------------
# Sectioning helper
# ---------------------------------------------------------------------------


def test_attribute_email_does_not_commit_mid_request(db_session):
    """#4051 — attribute_email must flush (not commit) the forwarding_seen_at
    stamps so outer-transaction atomicity is preserved. We verify by adding
    a marker row before calling attribute_email, then rolling back: if
    attribute_email had committed mid-request, the marker row would survive
    the rollback.
    """
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_SCHOOL_EMAIL,
        attribute_email,
    )
    m = _models()

    parent = _make_parent(db_session, "no_commit@test.com")
    profile = _make_profile(db_session, parent.id, "Tester")
    db_session.add(m["ParentChildSchoolEmail"](
        child_profile_id=profile.id,
        email_address="t@ocdsb.ca",
    ))
    db_session.commit()

    marker_email = "rollback_marker@test.com"

    # Marker row added INSIDE the uncommitted transaction.
    marker = m["User"](
        email=marker_email,
        full_name="Marker",
        role=m["UserRole"].PARENT,
        hashed_password=m["get_password_hash"]("Password123!"),
    )
    db_session.add(marker)
    db_session.flush()  # assign id, stay uncommitted

    # attribute_email stamps forwarding_seen_at on the matched school
    # email row. It MUST NOT commit — if it did, the marker row above
    # would become permanent.
    result = attribute_email(
        {"To": "t@ocdsb.ca"},
        parent.id,
        db_session,
    )
    assert result["source"] == ATTR_SOURCE_SCHOOL_EMAIL

    db_session.rollback()

    # After rollback, the marker row must be gone. If attribute_email
    # committed mid-request, it would have persisted.
    still_there = (
        db_session.query(m["User"])
        .filter(m["User"].email == marker_email)
        .first()
    )
    assert still_there is None, (
        "attribute_email appears to have committed the session mid-request; "
        "the marker row survived a rollback that should have wiped it."
    )


# ---------------------------------------------------------------------------
# MFIPPA (#4057) — exception-path log must not leak student school addresses
# ---------------------------------------------------------------------------


def test_attribute_email_flush_failure_does_not_log_raw_recipients(
    db_session, caplog, monkeypatch
):
    """When db.flush() fails in stage 1, the exception log must NOT contain
    the raw school email addresses (MFIPPA). It must contain parent_id and
    a recipient_count only.
    """
    import logging as _logging

    from app.services import unified_digest_attribution as uda
    from app.services.unified_digest_attribution import attribute_email
    m = _models()

    parent = _make_parent(db_session, "mfippa_attr@test.com")
    profile = _make_profile(db_session, parent.id, "Scrub")
    school_address = "scrub.student@ocdsb.ca"
    db_session.add(m["ParentChildSchoolEmail"](
        child_profile_id=profile.id,
        email_address=school_address,
    ))
    db_session.commit()

    # Force the flush to blow up so we exercise the exception log path.
    def _boom():
        raise RuntimeError("forced flush failure")

    monkeypatch.setattr(db_session, "flush", _boom)

    caplog.set_level(_logging.ERROR, logger=uda.logger.name)
    attribute_email(
        {"To": school_address},
        parent.id,
        db_session,
    )

    # Combine all captured log text (message + formatted record).
    combined = "\n".join(
        rec.getMessage() for rec in caplog.records
    ) + "\n" + caplog.text

    assert school_address not in combined, (
        f"Raw recipient email leaked into exception log: {combined!r}"
    )
    assert f"parent_id={parent.id}" in combined
    assert "recipient_count=1" in combined


def test_sectioning_groups_emails_by_attribution_source():
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_APPLIES_TO_ALL,
        ATTR_SOURCE_PARENT_DIRECT,
        ATTR_SOURCE_SCHOOL_EMAIL,
        ATTR_SOURCE_SENDER_TAG,
        ATTR_SOURCE_SENDER_TAG_AMBIGUOUS,
        ATTR_SOURCE_UNATTRIBUTED,
        build_sectioned_digest,
    )

    pairs = [
        ({"id": 1}, {"kid_ids": [10], "source": ATTR_SOURCE_SCHOOL_EMAIL}),
        ({"id": 2}, {"kid_ids": [10, 11], "source": ATTR_SOURCE_SCHOOL_EMAIL}),
        ({"id": 3}, {"kid_ids": [11], "source": ATTR_SOURCE_SENDER_TAG}),
        ({"id": 4}, {"kid_ids": [10, 11], "source": ATTR_SOURCE_APPLIES_TO_ALL}),
        ({"id": 5}, {"kid_ids": [], "source": ATTR_SOURCE_UNATTRIBUTED}),
        ({"id": 6}, {"kid_ids": [], "source": ATTR_SOURCE_PARENT_DIRECT}),
        ({"id": 7}, {"kid_ids": [10, 11], "source": ATTR_SOURCE_SENDER_TAG_AMBIGUOUS}),
    ]
    result = build_sectioned_digest(pairs)
    # multi-kid school_email + applies_to_all + sender_tag_ambiguous → for_all_kids
    ids_all = [e["id"] for e in result["for_all_kids"]]
    assert ids_all == [2, 4, 7]
    assert [e["id"] for e in result["per_kid"][10]] == [1]
    assert [e["id"] for e in result["per_kid"][11]] == [3]
    assert [e["id"] for e in result["unattributed"]] == [5]
    assert [e["id"] for e in result["parent_direct"]] == [6]


# ---------------------------------------------------------------------------
# #4329 — parent-direct + ambiguous + auto-discovery
# ---------------------------------------------------------------------------


def test_is_school_looking_address_heuristic():
    from app.services.unified_digest_attribution import is_school_looking_address

    # Positive — gapps.* domain
    assert is_school_looking_address("349017574@gapps.yrdsb.ca") is True
    # Positive — .edu
    assert is_school_looking_address("kid@example.edu") is True
    # Positive — .k12.
    assert is_school_looking_address("kid@school.k12.tx.us") is True
    # Positive — known Canadian school-board domains (#4336).
    assert is_school_looking_address("kid@ocdsb.ca") is True
    assert is_school_looking_address("kid@tdsb.on.ca") is True
    assert is_school_looking_address("kid@peelschools.org") is True
    assert is_school_looking_address("kid@dsbn.org") is True
    assert is_school_looking_address("kid@yrdsb.ca") is True
    assert is_school_looking_address("kid@dpcdsb.org") is True
    assert is_school_looking_address("kid@hwdsb.on.ca") is True
    assert is_school_looking_address("kid@wrdsb.ca") is True
    assert is_school_looking_address("kid@sd35.bc.ca") is True
    # Negative — gmail
    assert is_school_looking_address("parent@gmail.com") is False
    # Negative — automated mailbox in school domain
    assert is_school_looking_address("no-reply@gapps.yrdsb.ca") is False
    assert is_school_looking_address("noreply@example.edu") is False
    # Negative — empty / malformed
    assert is_school_looking_address("") is False
    assert is_school_looking_address("not-an-email") is False


def test_attribute_parent_direct_when_no_school_recipients(db_session):
    """#4329 — recipient list contains only the parent's gmail (or other
    non-school addresses) → parent_direct, kid_ids=[], even if From matches
    a registered monitored sender."""
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_PARENT_DIRECT,
        attribute_email,
    )
    m = _models()

    parent = _make_parent(db_session, "pd1@test.com")
    p1 = _make_profile(db_session, parent.id, "Solo")
    sender = m["ParentDigestMonitoredSender"](
        parent_id=parent.id,
        email_address="teacher@school.ca",
        applies_to_all=True,
    )
    db_session.add(sender)
    db_session.commit()

    result = attribute_email(
        {
            "To": "parent@gmail.com",
            "From": "teacher@school.ca",
        },
        parent.id,
        db_session,
    )
    assert result == {"kid_ids": [], "source": ATTR_SOURCE_PARENT_DIRECT}
    # Sanity — the parent has a kid but parent_direct skips kid attribution.
    assert p1.id


def test_attribute_school_email_match_still_wins_over_parent_direct(db_session):
    """Stage 1 short-circuits before the parent-direct check — a registered
    school address always attributes to its kid even if other recipients are
    parent-direct."""
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_SCHOOL_EMAIL,
        attribute_email,
    )
    m = _models()

    parent = _make_parent(db_session, "pdsmix@test.com")
    profile = _make_profile(db_session, parent.id, "Tracked")
    db_session.add(m["ParentChildSchoolEmail"](
        child_profile_id=profile.id,
        email_address="tracked@gapps.yrdsb.ca",
    ))
    db_session.commit()

    result = attribute_email(
        {"To": "parent@gmail.com, tracked@gapps.yrdsb.ca"},
        parent.id,
        db_session,
    )
    assert result["source"] == ATTR_SOURCE_SCHOOL_EMAIL
    assert result["kid_ids"] == [profile.id]


def test_record_discovery_inserts_unregistered_school_address(db_session):
    """#4329 — record_discovery surfaces unregistered school-looking To:
    addresses so the parent can assign them later."""
    from app.services.unified_digest_attribution import record_discovery
    m = _models()

    parent = _make_parent(db_session, "disc1@test.com")

    record_discovery(
        {
            "To": "349017574@gapps.yrdsb.ca, parent@gmail.com",
            "From": "Teacher <teacher@yrdsb.ca>",
        },
        parent.id,
        db_session,
    )
    db_session.commit()

    rows = (
        db_session.query(m["ParentDiscoveredSchoolEmail"])
        .filter(m["ParentDiscoveredSchoolEmail"].parent_id == parent.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].email_address == "349017574@gapps.yrdsb.ca"
    assert rows[0].sample_sender == "teacher@yrdsb.ca"
    assert rows[0].occurrences == 1


def test_record_discovery_skips_already_registered_address(db_session):
    """#4329 — addresses already registered under any kid of this parent
    should not be re-surfaced."""
    from app.services.unified_digest_attribution import record_discovery
    m = _models()

    parent = _make_parent(db_session, "disc2@test.com")
    profile = _make_profile(db_session, parent.id, "Known")
    db_session.add(m["ParentChildSchoolEmail"](
        child_profile_id=profile.id,
        email_address="known.kid@gapps.yrdsb.ca",
    ))
    db_session.commit()

    record_discovery(
        {
            "To": "known.kid@gapps.yrdsb.ca",
            "From": "teacher@yrdsb.ca",
        },
        parent.id,
        db_session,
    )
    db_session.commit()

    rows = (
        db_session.query(m["ParentDiscoveredSchoolEmail"])
        .filter(m["ParentDiscoveredSchoolEmail"].parent_id == parent.id)
        .all()
    )
    assert rows == []


def test_record_discovery_bumps_occurrences_on_repeat(db_session):
    from app.services.unified_digest_attribution import record_discovery
    m = _models()

    parent = _make_parent(db_session, "disc3@test.com")

    record_discovery(
        {"To": "kid@gapps.yrdsb.ca", "From": "first@yrdsb.ca"},
        parent.id,
        db_session,
    )
    db_session.commit()
    record_discovery(
        {"To": "kid@gapps.yrdsb.ca", "From": "second@yrdsb.ca"},
        parent.id,
        db_session,
    )
    db_session.commit()

    rows = (
        db_session.query(m["ParentDiscoveredSchoolEmail"])
        .filter(m["ParentDiscoveredSchoolEmail"].parent_id == parent.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].occurrences == 2
    # Latest sample_sender wins so the UX hint stays fresh.
    assert rows[0].sample_sender == "second@yrdsb.ca"


def test_record_discovery_skips_non_school_recipients(db_session):
    """Only school-looking domains qualify for discovery — gmail-only
    recipients are parent-direct and don't need to be classified."""
    from app.services.unified_digest_attribution import record_discovery
    m = _models()

    parent = _make_parent(db_session, "disc4@test.com")

    record_discovery(
        {"To": "parent@gmail.com", "From": "x@gmail.com"},
        parent.id,
        db_session,
    )
    db_session.commit()

    rows = (
        db_session.query(m["ParentDiscoveredSchoolEmail"])
        .filter(m["ParentDiscoveredSchoolEmail"].parent_id == parent.id)
        .all()
    )
    assert rows == []


# ---------------------------------------------------------------------------
# #4336 — Canadian school-board domain heuristic in attribution
# ---------------------------------------------------------------------------


def test_unregistered_ocdsb_recipient_falls_through_to_sender_tag(db_session):
    """#4336 — an ``ocdsb.ca`` recipient that isn't registered for any kid
    (so Stage 1 misses) must be classified as school-looking by the
    heuristic. With a monitored sender row in place, attribution should
    land on Stage 3 (sender-tag) rather than collapse to Stage 2
    (parent_direct)."""
    from app.services.unified_digest_attribution import (
        ATTR_SOURCE_APPLIES_TO_ALL,
        attribute_email,
    )
    m = _models()

    parent = _make_parent(db_session, "board1@test.com")
    p1 = _make_profile(db_session, parent.id, "Boardkid")
    sender = m["ParentDigestMonitoredSender"](
        parent_id=parent.id,
        email_address="teacher@school.ca",
        applies_to_all=True,
    )
    db_session.add(sender)
    db_session.commit()

    # The recipient isn't registered for any of the parent's kids, but
    # ocdsb.ca is now in the school-board allowlist — so we expect Stage 3
    # (sender-tag), not Stage 2 (parent_direct).
    result = attribute_email(
        {
            "To": "unregistered.kid@ocdsb.ca",
            "From": "teacher@school.ca",
        },
        parent.id,
        db_session,
    )
    assert result["source"] == ATTR_SOURCE_APPLIES_TO_ALL
    assert p1.id in result["kid_ids"]


# ---------------------------------------------------------------------------
# #4341 — record_discovery with pre-fetched registered set
# ---------------------------------------------------------------------------


def test_record_discovery_uses_pre_fetched_registered_set_skips_query(db_session):
    """#4341 — when the worker passes a pre-fetched ``registered_addresses``
    set, the function must NOT issue its own registered-rows SELECT and
    must respect the set when filtering candidates."""
    from app.services.unified_digest_attribution import record_discovery
    m = _models()

    parent = _make_parent(db_session, "cache1@test.com")

    record_discovery(
        {
            "To": "already.registered@gapps.yrdsb.ca, brand.new@gapps.yrdsb.ca",
            "From": "teacher@yrdsb.ca",
        },
        parent.id,
        db_session,
        registered_addresses={"already.registered@gapps.yrdsb.ca"},
    )
    db_session.commit()

    rows = (
        db_session.query(m["ParentDiscoveredSchoolEmail"])
        .filter(m["ParentDiscoveredSchoolEmail"].parent_id == parent.id)
        .all()
    )
    addresses = {r.email_address for r in rows}
    # The address present in the pre-fetched set is treated as registered
    # and dropped — only the brand-new address gets surfaced.
    assert addresses == {"brand.new@gapps.yrdsb.ca"}


def test_record_discovery_back_compat_without_kwarg(db_session):
    """#4341 — calling without ``registered_addresses`` still works (per-call
    DB query fallback for direct callers / tests)."""
    from app.services.unified_digest_attribution import record_discovery
    m = _models()

    parent = _make_parent(db_session, "cache2@test.com")

    record_discovery(
        {"To": "fresh@gapps.yrdsb.ca", "From": "teacher@yrdsb.ca"},
        parent.id,
        db_session,
    )
    db_session.commit()

    rows = (
        db_session.query(m["ParentDiscoveredSchoolEmail"])
        .filter(m["ParentDiscoveredSchoolEmail"].parent_id == parent.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].email_address == "fresh@gapps.yrdsb.ca"
