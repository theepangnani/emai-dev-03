"""Tests for the discovered-school-emails API endpoints (#4329).

Covers GET / POST(assign) / DELETE on
``/api/parent/email-digest/discovered-school-emails``.
"""

import pytest
from conftest import PASSWORD, _auth


PARENT_EMAIL = "discovered_parent@test.com"
OTHER_PARENT_EMAIL = "discovered_other_parent@test.com"
STUDENT_EMAIL = "discovered_student@test.com"

PREFIX = "/api/parent/email-digest"


@pytest.fixture()
def setup(db_session):
    """Create a parent with one child profile and a clean discovered-emails table."""
    from app.core.security import get_password_hash
    from app.models.parent_gmail_integration import (
        ParentChildProfile,
        ParentChildSchoolEmail,
        ParentDiscoveredSchoolEmail,
    )
    from app.models.user import User, UserRole

    parent = db_session.query(User).filter(User.email == PARENT_EMAIL).first()
    if not parent:
        parent = User(
            email=PARENT_EMAIL,
            full_name="Discovered Parent",
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
            full_name="Discovered Student",
            role=UserRole.STUDENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(student)
        db_session.commit()

    # Clean slate for both parents.
    db_session.query(ParentDiscoveredSchoolEmail).filter(
        ParentDiscoveredSchoolEmail.parent_id.in_([parent.id, other.id])
    ).delete(synchronize_session=False)
    db_session.query(ParentChildSchoolEmail).filter(
        ParentChildSchoolEmail.child_profile_id.in_(
            db_session.query(ParentChildProfile.id).filter(
                ParentChildProfile.parent_id.in_([parent.id, other.id])
            )
        )
    ).delete(synchronize_session=False)
    db_session.query(ParentChildProfile).filter(
        ParentChildProfile.parent_id.in_([parent.id, other.id])
    ).delete()
    db_session.commit()

    profile = ParentChildProfile(parent_id=parent.id, first_name="Haashini")
    db_session.add(profile)
    db_session.commit()

    return {
        "parent": parent,
        "other_parent": other,
        "student": student,
        "profile": profile,
    }


def _seed_discovery(db_session, parent_id, addr, **kwargs):
    from app.models.parent_gmail_integration import ParentDiscoveredSchoolEmail

    row = ParentDiscoveredSchoolEmail(
        parent_id=parent_id,
        email_address=addr,
        sample_sender=kwargs.get("sample_sender", "teacher@yrdsb.ca"),
        occurrences=kwargs.get("occurrences", 1),
    )
    db_session.add(row)
    db_session.commit()
    return row


# ---------------------------------------------------------------------------
# GET /discovered-school-emails
# ---------------------------------------------------------------------------


class TestListDiscovered:
    def test_returns_only_callers_rows(self, client, db_session, setup):
        _seed_discovery(db_session, setup["parent"].id, "mine@gapps.yrdsb.ca")
        _seed_discovery(
            db_session, setup["other_parent"].id, "other@gapps.yrdsb.ca"
        )
        headers = _auth(client, PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/discovered-school-emails", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        addresses = [d["email_address"] for d in data]
        assert "mine@gapps.yrdsb.ca" in addresses
        assert "other@gapps.yrdsb.ca" not in addresses

    def test_empty_list_when_none(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.get(f"{PREFIX}/discovered-school-emails", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unauthenticated(self, client, setup):
        resp = client.get(f"{PREFIX}/discovered-school-emails")
        assert resp.status_code in (401, 403)

    def test_wrong_role(self, client, setup):
        headers = _auth(client, STUDENT_EMAIL)
        resp = client.get(f"{PREFIX}/discovered-school-emails", headers=headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /discovered-school-emails/{id}/assign
# ---------------------------------------------------------------------------


class TestAssignDiscovered:
    def test_assign_moves_into_school_emails_and_deletes_discovery(
        self, client, db_session, setup
    ):
        from app.models.parent_gmail_integration import (
            ParentChildSchoolEmail,
            ParentDiscoveredSchoolEmail,
        )

        row = _seed_discovery(
            db_session, setup["parent"].id, "kid@gapps.yrdsb.ca"
        )
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(
            f"{PREFIX}/discovered-school-emails/{row.id}/assign",
            json={"child_profile_id": setup["profile"].id},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        # Discovery row gone.
        assert (
            db_session.query(ParentDiscoveredSchoolEmail)
            .filter(ParentDiscoveredSchoolEmail.id == row.id)
            .first()
            is None
        )
        # New school-email row exists for the kid.
        assert (
            db_session.query(ParentChildSchoolEmail)
            .filter(
                ParentChildSchoolEmail.child_profile_id == setup["profile"].id,
                ParentChildSchoolEmail.email_address == "kid@gapps.yrdsb.ca",
            )
            .first()
            is not None
        )

    def test_assign_idempotent_when_already_registered(
        self, client, db_session, setup
    ):
        from app.models.parent_gmail_integration import (
            ParentChildSchoolEmail,
            ParentDiscoveredSchoolEmail,
        )

        # Pre-register the address for the kid.
        db_session.add(ParentChildSchoolEmail(
            child_profile_id=setup["profile"].id,
            email_address="dup@gapps.yrdsb.ca",
        ))
        db_session.commit()
        row = _seed_discovery(
            db_session, setup["parent"].id, "dup@gapps.yrdsb.ca"
        )
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(
            f"{PREFIX}/discovered-school-emails/{row.id}/assign",
            json={"child_profile_id": setup["profile"].id},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        # Discovery row gone.
        assert (
            db_session.query(ParentDiscoveredSchoolEmail)
            .filter(ParentDiscoveredSchoolEmail.id == row.id)
            .first()
            is None
        )
        # No duplicate school_emails row.
        rows = (
            db_session.query(ParentChildSchoolEmail)
            .filter(
                ParentChildSchoolEmail.child_profile_id == setup["profile"].id,
                ParentChildSchoolEmail.email_address == "dup@gapps.yrdsb.ca",
            )
            .all()
        )
        assert len(rows) == 1

    def test_assign_404_when_discovery_owned_by_other_parent(
        self, client, db_session, setup
    ):
        row = _seed_discovery(
            db_session, setup["other_parent"].id, "stranger@gapps.yrdsb.ca"
        )
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(
            f"{PREFIX}/discovered-school-emails/{row.id}/assign",
            json={"child_profile_id": setup["profile"].id},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_assign_404_when_profile_owned_by_other_parent(
        self, client, db_session, setup
    ):
        from app.models.parent_gmail_integration import ParentChildProfile

        other_profile = ParentChildProfile(
            parent_id=setup["other_parent"].id,
            first_name="OtherKid",
        )
        db_session.add(other_profile)
        db_session.commit()
        row = _seed_discovery(
            db_session, setup["parent"].id, "moveme@gapps.yrdsb.ca"
        )
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(
            f"{PREFIX}/discovered-school-emails/{row.id}/assign",
            json={"child_profile_id": other_profile.id},
            headers=headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /discovered-school-emails/{id}
# ---------------------------------------------------------------------------


class TestDismissDiscovered:
    def test_dismiss_deletes_row(self, client, db_session, setup):
        from app.models.parent_gmail_integration import (
            ParentDiscoveredSchoolEmail,
        )

        row = _seed_discovery(
            db_session, setup["parent"].id, "bye@gapps.yrdsb.ca"
        )
        headers = _auth(client, PARENT_EMAIL)
        resp = client.delete(
            f"{PREFIX}/discovered-school-emails/{row.id}", headers=headers
        )
        assert resp.status_code == 204
        assert (
            db_session.query(ParentDiscoveredSchoolEmail)
            .filter(ParentDiscoveredSchoolEmail.id == row.id)
            .first()
            is None
        )

    def test_dismiss_404_when_owned_by_other_parent(
        self, client, db_session, setup
    ):
        row = _seed_discovery(
            db_session, setup["other_parent"].id, "leakage@gapps.yrdsb.ca"
        )
        headers = _auth(client, PARENT_EMAIL)
        resp = client.delete(
            f"{PREFIX}/discovered-school-emails/{row.id}", headers=headers
        )
        assert resp.status_code == 404
