"""Schema and backfill tests for unified digest v2 (#4012, #4013).

Covers:
- The 4 new parent-level tables exist and are created by ``Base.metadata.create_all``.
- Model CRUD + relationships + unique constraints.
- Backfill migration idempotently seeds new tables from legacy
  ``parent_gmail_integrations`` + ``parent_digest_monitored_emails`` rows.
"""

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.exc import IntegrityError


def _models():
    """Lazy import models so conftest's app fixture re-registers them first."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students
    from app.models.parent_gmail_integration import (
        ParentGmailIntegration,
        ParentDigestMonitoredEmail,
        ParentChildProfile,
        ParentChildSchoolEmail,
        ParentDigestMonitoredSender,
        SenderChildAssignment,
    )
    return {
        "get_password_hash": get_password_hash,
        "User": User, "UserRole": UserRole, "Student": Student, "parent_students": parent_students,
        "ParentGmailIntegration": ParentGmailIntegration,
        "ParentDigestMonitoredEmail": ParentDigestMonitoredEmail,
        "ParentChildProfile": ParentChildProfile,
        "ParentChildSchoolEmail": ParentChildSchoolEmail,
        "ParentDigestMonitoredSender": ParentDigestMonitoredSender,
        "SenderChildAssignment": SenderChildAssignment,
    }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def test_new_tables_exist_in_schema(db_session):
    inspector = sa_inspect(db_session.bind)
    tables = set(inspector.get_table_names())
    assert {
        "parent_child_profiles",
        "parent_child_school_emails",
        "parent_digest_monitored_senders",
        "sender_child_assignments",
    }.issubset(tables)


def test_parent_child_profile_columns(db_session):
    inspector = sa_inspect(db_session.bind)
    cols = {c["name"] for c in inspector.get_columns("parent_child_profiles")}
    assert {"id", "parent_id", "student_id", "first_name", "created_at"} <= cols


def test_school_email_columns(db_session):
    inspector = sa_inspect(db_session.bind)
    cols = {c["name"] for c in inspector.get_columns("parent_child_school_emails")}
    assert {"id", "child_profile_id", "email_address", "forwarding_seen_at", "created_at"} <= cols


def test_monitored_sender_columns(db_session):
    inspector = sa_inspect(db_session.bind)
    cols = {c["name"] for c in inspector.get_columns("parent_digest_monitored_senders")}
    assert {
        "id", "parent_id", "email_address", "sender_name", "label",
        "applies_to_all", "created_at",
    } <= cols


def test_sender_child_assignment_columns(db_session):
    inspector = sa_inspect(db_session.bind)
    cols = {c["name"] for c in inspector.get_columns("sender_child_assignments")}
    assert {"id", "sender_id", "child_profile_id", "created_at"} <= cols


# ---------------------------------------------------------------------------
# Model CRUD + relationships
# ---------------------------------------------------------------------------

def _make_parent(db, email="parent_v2@test.com"):
    m = _models()
    existing = db.query(m["User"]).filter(m["User"].email == email).first()
    if existing:
        return existing
    parent = m["User"](
        email=email,
        full_name="Digest Parent V2",
        role=m["UserRole"].PARENT,
        hashed_password=m["get_password_hash"]("Password123!"),
    )
    db.add(parent)
    db.commit()
    return parent


def test_create_child_profile_with_school_emails(db_session):
    m = _models()
    parent = _make_parent(db_session, "pcp_test@test.com")

    profile = m["ParentChildProfile"](parent_id=parent.id, first_name="Thanushan")
    db_session.add(profile)
    db_session.commit()

    email = m["ParentChildSchoolEmail"](
        child_profile_id=profile.id,
        email_address="thanushan@ocdsb.ca",
    )
    db_session.add(email)
    db_session.commit()

    assert len(profile.school_emails) == 1
    assert profile.school_emails[0].email_address == "thanushan@ocdsb.ca"
    assert profile.school_emails[0].forwarding_seen_at is None


def test_monitored_sender_with_assignments(db_session):
    m = _models()
    parent = _make_parent(db_session, "pms_test@test.com")

    p1 = m["ParentChildProfile"](parent_id=parent.id, first_name="Thanushan")
    p2 = m["ParentChildProfile"](parent_id=parent.id, first_name="Haashini")
    db_session.add_all([p1, p2])
    db_session.commit()

    sender = m["ParentDigestMonitoredSender"](
        parent_id=parent.id,
        email_address="bill.hogarth.ss@yrdsb.ca",
        sender_name="Bill Hogarth SS",
        label="school",
    )
    db_session.add(sender)
    db_session.commit()

    db_session.add_all([
        m["SenderChildAssignment"](sender_id=sender.id, child_profile_id=p1.id),
        m["SenderChildAssignment"](sender_id=sender.id, child_profile_id=p2.id),
    ])
    db_session.commit()

    db_session.refresh(sender)
    assert len(sender.child_assignments) == 2
    assigned_profiles = {a.child_profile.first_name for a in sender.child_assignments}
    assert assigned_profiles == {"Thanushan", "Haashini"}


def test_applies_to_all_default_false(db_session):
    m = _models()
    parent = _make_parent(db_session, "apply_test@test.com")
    sender = m["ParentDigestMonitoredSender"](
        parent_id=parent.id,
        email_address="noreply@classroom.google.com",
    )
    db_session.add(sender)
    db_session.commit()
    db_session.refresh(sender)
    assert sender.applies_to_all is False


# ---------------------------------------------------------------------------
# Unique constraints
# ---------------------------------------------------------------------------

def test_duplicate_sender_email_for_same_parent_rejected(db_session):
    m = _models()
    parent = _make_parent(db_session, "dup_sender@test.com")
    db_session.add(m["ParentDigestMonitoredSender"](
        parent_id=parent.id,
        email_address="teacher@school.ca",
    ))
    db_session.commit()

    db_session.add(m["ParentDigestMonitoredSender"](
        parent_id=parent.id,
        email_address="teacher@school.ca",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicate_assignment_rejected(db_session):
    m = _models()
    parent = _make_parent(db_session, "dup_assign@test.com")
    profile = m["ParentChildProfile"](parent_id=parent.id, first_name="Solo")
    db_session.add(profile)
    db_session.commit()

    sender = m["ParentDigestMonitoredSender"](parent_id=parent.id, email_address="x@y.ca")
    db_session.add(sender)
    db_session.commit()

    db_session.add(m["SenderChildAssignment"](sender_id=sender.id, child_profile_id=profile.id))
    db_session.commit()

    db_session.add(m["SenderChildAssignment"](sender_id=sender.id, child_profile_id=profile.id))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicate_school_email_for_same_profile_rejected(db_session):
    m = _models()
    parent = _make_parent(db_session, "dup_school_email@test.com")
    profile = m["ParentChildProfile"](parent_id=parent.id, first_name="A")
    db_session.add(profile)
    db_session.commit()

    db_session.add(m["ParentChildSchoolEmail"](
        child_profile_id=profile.id,
        email_address="a@ocdsb.ca",
    ))
    db_session.commit()

    db_session.add(m["ParentChildSchoolEmail"](
        child_profile_id=profile.id,
        email_address="a@ocdsb.ca",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------------
# Backfill migration (idempotent seed from legacy rows)
# ---------------------------------------------------------------------------

def _seed_legacy_world(db):
    """Create a parent + two kids + legacy integrations + legacy monitored emails.

    Idempotent: safe to call across multiple tests sharing the session-scoped
    SQLite DB; reuses existing rows by email/key rather than re-creating.

    #4253 — uses a uniquely-scoped parent email to avoid colliding with
    ``test_parent_email_digest_job.py::test_digest_sectioned_legacy_blob_falls_back_to_legacy_html``,
    which generates a parent named ``legacy_parent@test.com`` (via
    ``email_suffix="legacy"``) and attaches an "Alex" integration to it. That
    parent persists in the session-scoped DB and pollutes our backfill query.
    """
    m = _models()
    parent = _make_parent(db, "v2_backfill_parent@test.com")

    def _get_or_create_user(email, full_name):
        existing = db.query(m["User"]).filter(m["User"].email == email).first()
        if existing:
            return existing
        u = m["User"](
            email=email,
            full_name=full_name,
            role=m["UserRole"].STUDENT,
            hashed_password=m["get_password_hash"]("Password123!"),
        )
        db.add(u)
        db.commit()
        return u

    t = _get_or_create_user("thanushan.ocdsb@test.com", "Thanushan Gnanasabapathy")
    h = _get_or_create_user("haashini.frankln@test.com", "Haashini Gnanasabapathy")

    def _get_or_create_student(user_id, grade):
        existing = db.query(m["Student"]).filter(m["Student"].user_id == user_id).first()
        if existing:
            return existing
        st = m["Student"](user_id=user_id, grade_level=grade)
        db.add(st)
        db.commit()
        return st

    t_student = _get_or_create_student(t.id, 10)
    h_student = _get_or_create_student(h.id, 8)

    for st in (t_student, h_student):
        existing_link = db.execute(
            m["parent_students"].select().where(
                (m["parent_students"].c.parent_id == parent.id)
                & (m["parent_students"].c.student_id == st.id)
            )
        ).first()
        if existing_link is None:
            db.execute(
                m["parent_students"].insert().values(parent_id=parent.id, student_id=st.id)
            )
    db.commit()

    def _get_or_create_integration(child_first_name, child_school_email):
        existing = (
            db.query(m["ParentGmailIntegration"])
            .filter(
                m["ParentGmailIntegration"].parent_id == parent.id,
                m["ParentGmailIntegration"].child_school_email == child_school_email,
            )
            .first()
        )
        if existing:
            return existing
        ig = m["ParentGmailIntegration"](
            parent_id=parent.id,
            gmail_address="parent@gmail.com",
            child_school_email=child_school_email,
            child_first_name=child_first_name,
        )
        db.add(ig)
        db.commit()
        return ig

    integ_t = _get_or_create_integration("Thanushan", "thanushan@ocdsb.ca")
    integ_h = _get_or_create_integration("Haashini", "haashini@frankln.ca")

    def _get_or_create_monitored(integration_id, email_address, sender_name, label):
        existing = (
            db.query(m["ParentDigestMonitoredEmail"])
            .filter(
                m["ParentDigestMonitoredEmail"].integration_id == integration_id,
                m["ParentDigestMonitoredEmail"].email_address == email_address,
            )
            .first()
        )
        if existing:
            return existing
        me = m["ParentDigestMonitoredEmail"](
            integration_id=integration_id,
            email_address=email_address,
            sender_name=sender_name,
            label=label,
        )
        db.add(me)
        db.commit()
        return me

    _get_or_create_monitored(integ_t.id, "bill.hogarth.ss@yrdsb.ca", "Bill Hogarth SS", "school")
    _get_or_create_monitored(integ_h.id, "bill.hogarth.ss@yrdsb.ca", "Bill Hogarth SS", "school")
    _get_or_create_monitored(integ_h.id, "counselor@frankln.ca", "Varun Kunar", "counselor")

    return {"parent": parent, "integ_t": integ_t, "integ_h": integ_h, "t": t, "h": h}


def _run_backfill(db):
    """Invoke the v2 backfill migration directly against the test DB."""
    from app.db import migrations  # noqa: F401 — module under test
    from app.core.config import settings
    import logging

    # Run the full migrations inner function — the v2 block is at the end
    # and other blocks are idempotent no-ops on a fresh test schema.
    # We call just the v2 block to keep the test focused.
    from sqlalchemy import text

    conn = db.bind.connect()
    try:
        # Abbreviated mirror of the v2 block in migrations.py. If the real
        # block changes shape, this test will drift — but the intent here
        # is to verify the backfill SQL is correct. An integration-level
        # test on a real Cloud Run startup would catch drift.
        conn.execute(text(
            """
            INSERT INTO parent_child_profiles (parent_id, student_id, first_name, created_at)
            SELECT parent_id, student_id, MIN(first_name) AS first_name, MIN(created_at) AS created_at
            FROM (
                SELECT DISTINCT
                    pgi.parent_id,
                    (
                        SELECT s.id
                        FROM users s
                        JOIN students st ON st.user_id = s.id
                        JOIN parent_students ps ON ps.student_id = st.id
                        WHERE ps.parent_id = pgi.parent_id
                          AND LOWER(SUBSTR(s.full_name, 1, INSTR(s.full_name || ' ', ' ') - 1)) = LOWER(pgi.child_first_name)
                        LIMIT 1
                    ) AS student_id,
                    LOWER(pgi.child_first_name) AS first_name_lower,
                    pgi.child_first_name AS first_name,
                    pgi.created_at
                FROM parent_gmail_integrations pgi
                WHERE pgi.child_first_name IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM parent_child_profiles pcp
                      WHERE pcp.parent_id = pgi.parent_id
                        AND LOWER(pcp.first_name) = LOWER(pgi.child_first_name)
                  )
            ) dedup
            GROUP BY parent_id, student_id, first_name_lower
            """
        ))
        conn.execute(text(
            """
            INSERT INTO parent_child_school_emails (child_profile_id, email_address, forwarding_seen_at, created_at)
            SELECT pcp.id, LOWER(pgi.child_school_email), NULL, pgi.created_at
            FROM parent_gmail_integrations pgi
            JOIN parent_child_profiles pcp
              ON pcp.parent_id = pgi.parent_id
             AND LOWER(pcp.first_name) = LOWER(pgi.child_first_name)
            WHERE pgi.child_school_email IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM parent_child_school_emails pcse
                  WHERE pcse.child_profile_id = pcp.id
                    AND LOWER(pcse.email_address) = LOWER(pgi.child_school_email)
              )
            """
        ))
        conn.execute(text(
            """
            INSERT INTO parent_digest_monitored_senders (parent_id, email_address, sender_name, label, applies_to_all, created_at)
            SELECT DISTINCT
                pgi.parent_id,
                LOWER(pdme.email_address),
                pdme.sender_name,
                pdme.label,
                0,
                pdme.created_at
            FROM parent_digest_monitored_emails pdme
            JOIN parent_gmail_integrations pgi
              ON pgi.id = pdme.integration_id
            WHERE pdme.email_address IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM parent_digest_monitored_senders pdms
                  WHERE pdms.parent_id = pgi.parent_id
                    AND LOWER(pdms.email_address) = LOWER(pdme.email_address)
              )
            """
        ))
        conn.execute(text(
            """
            INSERT INTO sender_child_assignments (sender_id, child_profile_id, created_at)
            SELECT DISTINCT pdms.id, pcp.id, pdme.created_at
            FROM parent_digest_monitored_emails pdme
            JOIN parent_gmail_integrations pgi ON pgi.id = pdme.integration_id
            JOIN parent_child_profiles pcp
              ON pcp.parent_id = pgi.parent_id
             AND LOWER(pcp.first_name) = LOWER(pgi.child_first_name)
            JOIN parent_digest_monitored_senders pdms
              ON pdms.parent_id = pgi.parent_id
             AND LOWER(pdms.email_address) = LOWER(pdme.email_address)
            WHERE NOT EXISTS (
                SELECT 1 FROM sender_child_assignments sca
                WHERE sca.sender_id = pdms.id
                  AND sca.child_profile_id = pcp.id
            )
            """
        ))
        conn.commit()
    finally:
        conn.close()


def test_backfill_creates_profiles_linked_to_students(db_session):
    m = _models()
    world = _seed_legacy_world(db_session)
    _run_backfill(db_session)

    profiles = (
        db_session.query(m["ParentChildProfile"])
        .filter(m["ParentChildProfile"].parent_id == world["parent"].id)
        .all()
    )
    names = {p.first_name for p in profiles}
    assert names == {"Thanushan", "Haashini"}
    linked_ids = {p.student_id for p in profiles if p.student_id is not None}
    assert linked_ids == {world["t"].id, world["h"].id}


def test_backfill_creates_school_emails(db_session):
    m = _models()
    world = _seed_legacy_world(db_session)
    _run_backfill(db_session)

    emails = (
        db_session.query(m["ParentChildSchoolEmail"])
        .join(m["ParentChildProfile"], m["ParentChildProfile"].id == m["ParentChildSchoolEmail"].child_profile_id)
        .filter(m["ParentChildProfile"].parent_id == world["parent"].id)
        .all()
    )
    addresses = {e.email_address for e in emails}
    assert addresses == {"thanushan@ocdsb.ca", "haashini@frankln.ca"}
    assert all(e.forwarding_seen_at is None for e in emails)


def test_backfill_dedupes_senders_across_integrations(db_session):
    m = _models()
    world = _seed_legacy_world(db_session)
    _run_backfill(db_session)

    senders = (
        db_session.query(m["ParentDigestMonitoredSender"])
        .filter(m["ParentDigestMonitoredSender"].parent_id == world["parent"].id)
        .all()
    )
    addresses = sorted(s.email_address for s in senders)
    # Bill Hogarth SS appears twice in legacy (once per integration) but
    # should be a single row in the unified table.
    assert addresses == [
        "bill.hogarth.ss@yrdsb.ca",
        "counselor@frankln.ca",
    ]


def test_backfill_creates_multi_kid_assignment_for_shared_sender(db_session):
    m = _models()
    world = _seed_legacy_world(db_session)
    _run_backfill(db_session)

    bill = (
        db_session.query(m["ParentDigestMonitoredSender"])
        .filter(
            m["ParentDigestMonitoredSender"].parent_id == world["parent"].id,
            m["ParentDigestMonitoredSender"].email_address == "bill.hogarth.ss@yrdsb.ca",
        )
        .one()
    )
    assignments = bill.child_assignments
    assigned_names = {a.child_profile.first_name for a in assignments}
    assert assigned_names == {"Thanushan", "Haashini"}


def test_backfill_is_idempotent(db_session):
    m = _models()
    _seed_legacy_world(db_session)
    _run_backfill(db_session)
    before = (
        db_session.query(m["ParentChildProfile"]).count(),
        db_session.query(m["ParentChildSchoolEmail"]).count(),
        db_session.query(m["ParentDigestMonitoredSender"]).count(),
        db_session.query(m["SenderChildAssignment"]).count(),
    )
    # Run again — must not duplicate rows.
    _run_backfill(db_session)
    after = (
        db_session.query(m["ParentChildProfile"]).count(),
        db_session.query(m["ParentChildSchoolEmail"]).count(),
        db_session.query(m["ParentDigestMonitoredSender"]).count(),
        db_session.query(m["SenderChildAssignment"]).count(),
    )
    assert before == after, f"backfill not idempotent: {before} != {after}"


def test_backfill_case_differing_first_names_dedupe_to_single_profile(db_session):
    """Regression for #4047: two integrations with "Emma" and "emma" must
    produce exactly ONE parent_child_profiles row (pre-normalization GROUP
    BY on LOWER(first_name))."""
    m = _models()
    parent = _make_parent(db_session, "case_dedupe_parent@test.com")

    # Clean slate for this parent's v2 profiles
    db_session.query(m["ParentChildProfile"]).filter(
        m["ParentChildProfile"].parent_id == parent.id,
    ).delete()
    db_session.commit()

    # Two legacy integrations — same kid's name but different casings.
    ig1 = m["ParentGmailIntegration"](
        parent_id=parent.id,
        gmail_address="case_parent_a@gmail.com",
        child_school_email="emma_a@school.ca",
        child_first_name="Emma",
    )
    ig2 = m["ParentGmailIntegration"](
        parent_id=parent.id,
        gmail_address="case_parent_b@gmail.com",
        child_school_email="emma_b@school.ca",
        child_first_name="emma",
    )
    db_session.add_all([ig1, ig2])
    db_session.commit()

    _run_backfill(db_session)

    profiles = (
        db_session.query(m["ParentChildProfile"])
        .filter(m["ParentChildProfile"].parent_id == parent.id)
        .all()
    )
    assert len(profiles) == 1, (
        f"expected 1 profile after case-differing dedupe, got {len(profiles)}: "
        f"{[p.first_name for p in profiles]}"
    )
    assert profiles[0].first_name in {"Emma", "emma"}
