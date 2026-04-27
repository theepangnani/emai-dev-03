"""Idempotency + denylist tests for unified-v2 school-email backfill (#4328, #4099).

The unified-digest-v2 backfill in ``app/db/migrations.py`` previously re-seeded
``parent_child_school_emails`` from ``parent_gmail_integrations.child_school_email``
on every Cloud Run cold start. A user deleting a school-email row via the UI
would see it re-appear after the next deploy because the backfill's
``NOT EXISTS`` guard cannot distinguish "never seeded" from "user deleted".

The fix adds:
  * an ``unified_v2_backfilled_at`` column on ``parent_gmail_integrations``;
    the backfill skips already-stamped integrations.
  * a denylist (``no-reply@*``, ``noreply@*``, ``donotreply@*``,
    ``mailer-daemon@*``) at insert time so junk values from the legacy setup
    wizard are never seeded into the new table.
  * a one-time scrub deleting pre-existing junk rows from
    ``parent_child_school_emails``.

These tests run the actual ``_run_migrations_inner`` so we exercise the real
SQL block instead of a hand-rolled mirror.
"""

import logging

import pytest
from sqlalchemy import text


def _models():
    """Lazy import so conftest's app fixture re-registers them first."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.parent_gmail_integration import (
        ParentGmailIntegration,
        ParentChildProfile,
        ParentChildSchoolEmail,
    )
    return {
        "get_password_hash": get_password_hash,
        "User": User,
        "UserRole": UserRole,
        "ParentGmailIntegration": ParentGmailIntegration,
        "ParentChildProfile": ParentChildProfile,
        "ParentChildSchoolEmail": ParentChildSchoolEmail,
    }


def _make_parent(db, email):
    m = _models()
    existing = db.query(m["User"]).filter(m["User"].email == email).first()
    if existing:
        return existing
    p = m["User"](
        email=email,
        full_name="Backfill Parent",
        role=m["UserRole"].PARENT,
        hashed_password=m["get_password_hash"]("Password123!"),
    )
    db.add(p)
    db.commit()
    return p


def _make_integration(db, parent_id, child_first_name, child_school_email):
    m = _models()
    ig = m["ParentGmailIntegration"](
        parent_id=parent_id,
        gmail_address=f"{child_first_name.lower()}_parent@gmail.com",
        child_school_email=child_school_email,
        child_first_name=child_first_name,
    )
    db.add(ig)
    db.commit()
    return ig


def _run_migrations_against_session(db_session):
    """Run the real ``_run_migrations_inner`` against the test SQLite engine.

    This exercises the actual production SQL — not a hand-rolled mirror —
    so any drift in the real block surfaces here.
    """
    from app.core.config import settings
    from app.db import migrations as migrations_module

    logger = logging.getLogger("test_school_email_backfill")
    migrations_module._run_migrations_inner(db_session.bind, settings, logger)


def _count_school_emails(db, parent_id, email_address=None):
    m = _models()
    q = (
        db.query(m["ParentChildSchoolEmail"])
        .join(
            m["ParentChildProfile"],
            m["ParentChildProfile"].id == m["ParentChildSchoolEmail"].child_profile_id,
        )
        .filter(m["ParentChildProfile"].parent_id == parent_id)
    )
    if email_address is not None:
        q = q.filter(m["ParentChildSchoolEmail"].email_address == email_address.lower())
    return q.count()


# ---------------------------------------------------------------------------
# Test 1: delete then re-run migrations does NOT re-create the row
# ---------------------------------------------------------------------------

def test_user_delete_is_not_re_seeded_on_next_migration(db_session):
    """A user deleting a school-email row must NOT have it re-seeded by
    the backfill on the next Cloud Run cold start."""
    m = _models()
    parent = _make_parent(db_session, "delete_then_remigrate@test.com")
    _make_integration(db_session, parent.id, "Aarav", "real-email@school.ca")

    # First migration run — seeds the row.
    _run_migrations_against_session(db_session)
    assert _count_school_emails(db_session, parent.id, "real-email@school.ca") == 1

    # Simulate user clicking the × button in the digest UI.
    db_session.query(m["ParentChildSchoolEmail"]).filter(
        m["ParentChildSchoolEmail"].email_address == "real-email@school.ca",
    ).delete()
    db_session.commit()
    assert _count_school_emails(db_session, parent.id, "real-email@school.ca") == 0

    # Second migration run — must NOT re-seed.
    _run_migrations_against_session(db_session)
    db_session.expire_all()
    assert _count_school_emails(db_session, parent.id, "real-email@school.ca") == 0, (
        "user-deleted school email was re-seeded by the backfill"
    )


# ---------------------------------------------------------------------------
# Test 2: denylist filter never re-seeds junk
# ---------------------------------------------------------------------------

def test_denylist_blocks_junk_school_email_seed(db_session):
    """A legacy integration whose ``child_school_email`` matches the denylist
    (e.g. ``no-reply@classroom.google.com``) must never produce a row in
    ``parent_child_school_emails``."""
    parent = _make_parent(db_session, "denylist_seed@test.com")
    _make_integration(db_session, parent.id, "Bina", "no-reply@classroom.google.com")

    _run_migrations_against_session(db_session)

    assert _count_school_emails(db_session, parent.id) == 0, (
        "denylisted school email was inserted into parent_child_school_emails"
    )


# ---------------------------------------------------------------------------
# Test 3: data scrub removes pre-existing junk rows
# ---------------------------------------------------------------------------

def test_data_scrub_removes_pre_existing_junk_rows(db_session):
    """Junk rows already in ``parent_child_school_emails`` from earlier
    backfill runs must be deleted by the one-time scrub on the next
    migration run."""
    m = _models()
    parent = _make_parent(db_session, "scrub_pre_existing@test.com")

    # Pre-seed a profile and a junk school-email row directly — simulates
    # the state of a Cloud Run instance that ran the old, broken backfill.
    profile = m["ParentChildProfile"](parent_id=parent.id, first_name="Cara")
    db_session.add(profile)
    db_session.commit()

    junk = m["ParentChildSchoolEmail"](
        child_profile_id=profile.id,
        email_address="no-reply@classroom.google.com",
    )
    db_session.add(junk)
    db_session.commit()
    assert _count_school_emails(db_session, parent.id, "no-reply@classroom.google.com") == 1

    _run_migrations_against_session(db_session)
    db_session.expire_all()

    assert _count_school_emails(db_session, parent.id, "no-reply@classroom.google.com") == 0, (
        "pre-existing junk school-email row was not scrubbed"
    )


# ---------------------------------------------------------------------------
# Test 4: scrub is idempotent — running migrations twice raises no errors
# ---------------------------------------------------------------------------

def test_scrub_is_idempotent(db_session):
    """Running migrations twice in a row must not error and must leave
    a denylisted row absent both times."""
    m = _models()
    parent = _make_parent(db_session, "scrub_idempotent@test.com")

    profile = m["ParentChildProfile"](parent_id=parent.id, first_name="Darshini")
    db_session.add(profile)
    db_session.commit()

    db_session.add(m["ParentChildSchoolEmail"](
        child_profile_id=profile.id,
        email_address="donotreply@some-vendor.example.com",
    ))
    db_session.commit()

    _run_migrations_against_session(db_session)
    _run_migrations_against_session(db_session)  # second run — no error.

    db_session.expire_all()
    assert _count_school_emails(
        db_session, parent.id, "donotreply@some-vendor.example.com"
    ) == 0


# ---------------------------------------------------------------------------
# Test 5: real school emails are not affected
# ---------------------------------------------------------------------------

def test_real_school_email_seeded_and_not_duplicated(db_session):
    """A non-denylisted ``child_school_email`` must produce a row on first
    migration run and must not be duplicated on subsequent runs."""
    parent = _make_parent(db_session, "real_school_email@test.com")
    _make_integration(db_session, parent.id, "Esha", "student@gapps.yrdsb.ca")

    _run_migrations_against_session(db_session)
    assert _count_school_emails(db_session, parent.id, "student@gapps.yrdsb.ca") == 1

    # Second run — still present, not duplicated.
    _run_migrations_against_session(db_session)
    db_session.expire_all()
    assert _count_school_emails(db_session, parent.id, "student@gapps.yrdsb.ca") == 1


# ---------------------------------------------------------------------------
# Stamp behavior: integrations whose child_school_email is set get stamped
# ---------------------------------------------------------------------------

def test_unified_v2_backfilled_at_stamped_for_real_emails(db_session):
    """Integrations with a non-denylisted ``child_school_email`` must have
    ``unified_v2_backfilled_at`` set after the first migration run, so the
    next run skips them."""
    m = _models()
    parent = _make_parent(db_session, "stamp_real_email@test.com")
    integ = _make_integration(db_session, parent.id, "Faiza", "faiza@school.ca")
    assert integ.unified_v2_backfilled_at is None

    _run_migrations_against_session(db_session)

    db_session.expire(integ)
    refreshed = db_session.query(m["ParentGmailIntegration"]).get(integ.id)
    assert refreshed.unified_v2_backfilled_at is not None, (
        "integration was not stamped after backfill"
    )


def test_unified_v2_backfilled_at_not_stamped_for_denylisted(db_session):
    """Integrations whose ``child_school_email`` is denylisted must NOT be
    stamped — leaving them stamped would mask future legitimate values
    that happen to land in the column."""
    m = _models()
    parent = _make_parent(db_session, "stamp_denylisted@test.com")
    integ = _make_integration(db_session, parent.id, "Gita", "no-reply@classroom.google.com")

    _run_migrations_against_session(db_session)

    db_session.expire(integ)
    refreshed = db_session.query(m["ParentGmailIntegration"]).get(integ.id)
    assert refreshed.unified_v2_backfilled_at is None, (
        "denylisted integration was stamped — should remain NULL"
    )
