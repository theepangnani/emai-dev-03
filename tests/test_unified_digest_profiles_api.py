"""Tests for unified digest v2 child profiles + school emails API (#4014).

Covers GET /api/parent/child-profiles and POST/DELETE on
/api/parent/child-profiles/{id}/school-emails.
"""

from datetime import datetime, timezone

import pytest
from conftest import PASSWORD, _auth


PARENT_EMAIL = "profiles_parent@test.com"
OTHER_PARENT_EMAIL = "profiles_other_parent@test.com"
STUDENT_EMAIL = "profiles_student@test.com"


@pytest.fixture()
def setup(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.parent_gmail_integration import (
        ParentChildProfile,
        ParentChildSchoolEmail,
    )

    parent = db_session.query(User).filter(User.email == PARENT_EMAIL).first()
    if not parent:
        parent = User(
            email=PARENT_EMAIL,
            full_name="Profiles Parent",
            role=UserRole.PARENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(parent)
        db_session.commit()

    other = db_session.query(User).filter(User.email == OTHER_PARENT_EMAIL).first()
    if not other:
        other = User(
            email=OTHER_PARENT_EMAIL,
            full_name="Other Profiles Parent",
            role=UserRole.PARENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(other)
        db_session.commit()

    student = db_session.query(User).filter(User.email == STUDENT_EMAIL).first()
    if not student:
        student = User(
            email=STUDENT_EMAIL,
            full_name="Profiles Student",
            role=UserRole.STUDENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(student)
        db_session.commit()

    # Clean slate
    db_session.query(ParentChildSchoolEmail).filter(
        ParentChildSchoolEmail.child_profile_id.in_(
            db_session.query(ParentChildProfile.id).filter(
                ParentChildProfile.parent_id == parent.id,
            )
        )
    ).delete(synchronize_session=False)
    db_session.query(ParentChildProfile).filter(
        ParentChildProfile.parent_id == parent.id,
    ).delete()
    db_session.commit()

    profile_a = ParentChildProfile(parent_id=parent.id, first_name="Alex")
    profile_b = ParentChildProfile(parent_id=parent.id, first_name="Jordan")
    db_session.add_all([profile_a, profile_b])
    db_session.commit()

    existing = ParentChildSchoolEmail(
        child_profile_id=profile_a.id,
        email_address="alex@school.ca",
        forwarding_seen_at=datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc),
    )
    db_session.add(existing)
    db_session.commit()

    return {
        "parent": parent,
        "other_parent": other,
        "student": student,
        "profile_a": profile_a,
        "profile_b": profile_b,
    }


PREFIX = "/api/parent/child-profiles"


# ---------------------------------------------------------------------------
# GET /child-profiles
# ---------------------------------------------------------------------------


class TestListProfiles:
    def test_list_returns_own_profiles_with_school_emails(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.get(PREFIX, headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        names = {p["first_name"] for p in data}
        assert names == {"Alex", "Jordan"}

        alex = next(p for p in data if p["first_name"] == "Alex")
        assert len(alex["school_emails"]) == 1
        assert alex["school_emails"][0]["email_address"] == "alex@school.ca"
        assert alex["school_emails"][0]["forwarding_seen_at"] is not None

        jordan = next(p for p in data if p["first_name"] == "Jordan")
        assert jordan["school_emails"] == []

    def test_list_does_not_leak_other_parents(self, client, db_session, setup):
        from app.models.parent_gmail_integration import ParentChildProfile

        db_session.add(ParentChildProfile(
            parent_id=setup["other_parent"].id,
            first_name="ShouldNotAppear",
        ))
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.get(PREFIX, headers=headers)
        names = {p["first_name"] for p in resp.json()}
        assert "ShouldNotAppear" not in names

    def test_list_unauthenticated(self, client, setup):
        resp = client.get(PREFIX)
        assert resp.status_code in (401, 403)

    def test_list_wrong_role(self, client, setup):
        headers = _auth(client, STUDENT_EMAIL)
        resp = client.get(PREFIX, headers=headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /child-profiles/{id}/school-emails
# ---------------------------------------------------------------------------


class TestAddSchoolEmail:
    def test_add_school_email(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        pid = setup["profile_b"].id
        resp = client.post(
            f"{PREFIX}/{pid}/school-emails",
            json={"email_address": "Jordan@School.ca"},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["email_address"] == "jordan@school.ca"  # lower-cased
        assert data["forwarding_seen_at"] is None

    def test_add_duplicate_returns_409(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        pid = setup["profile_a"].id
        # profile_a already has alex@school.ca from fixture
        resp = client.post(
            f"{PREFIX}/{pid}/school-emails",
            json={"email_address": "alex@school.ca"},
            headers=headers,
        )
        assert resp.status_code == 409

    def test_add_duplicate_case_insensitive(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        pid = setup["profile_a"].id
        resp = client.post(
            f"{PREFIX}/{pid}/school-emails",
            json={"email_address": "ALEX@school.ca"},
            headers=headers,
        )
        assert resp.status_code == 409

    def test_add_invalid_email(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        pid = setup["profile_b"].id
        resp = client.post(
            f"{PREFIX}/{pid}/school-emails",
            json={"email_address": "not-an-email"},
            headers=headers,
        )
        assert resp.status_code == 422

    def test_add_nonexistent_profile(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(
            f"{PREFIX}/999999/school-emails",
            json={"email_address": "x@y.ca"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_add_other_parents_profile(self, client, db_session, setup):
        from app.models.parent_gmail_integration import ParentChildProfile

        other = ParentChildProfile(
            parent_id=setup["other_parent"].id,
            first_name="OtherKid",
        )
        db_session.add(other)
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.post(
            f"{PREFIX}/{other.id}/school-emails",
            json={"email_address": "x@y.ca"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_add_unauthenticated(self, client, setup):
        pid = setup["profile_b"].id
        resp = client.post(
            f"{PREFIX}/{pid}/school-emails",
            json={"email_address": "x@y.ca"},
        )
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# DELETE /child-profiles/{id}/school-emails/{email_id}
# ---------------------------------------------------------------------------


class TestDeleteSchoolEmail:
    def test_delete_own_school_email(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        pid = setup["profile_b"].id
        add = client.post(
            f"{PREFIX}/{pid}/school-emails",
            json={"email_address": "del@school.ca"},
            headers=headers,
        )
        eid = add.json()["id"]
        resp = client.delete(f"{PREFIX}/{pid}/school-emails/{eid}", headers=headers)
        assert resp.status_code == 204

    def test_delete_nonexistent_email(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        pid = setup["profile_b"].id
        resp = client.delete(f"{PREFIX}/{pid}/school-emails/999999", headers=headers)
        assert resp.status_code == 404

    def test_delete_email_on_other_parents_profile(self, client, db_session, setup):
        from app.models.parent_gmail_integration import (
            ParentChildProfile,
            ParentChildSchoolEmail,
        )

        other = ParentChildProfile(
            parent_id=setup["other_parent"].id,
            first_name="OtherKid",
        )
        db_session.add(other)
        db_session.commit()
        se = ParentChildSchoolEmail(
            child_profile_id=other.id,
            email_address="leak@school.ca",
        )
        db_session.add(se)
        db_session.commit()

        headers = _auth(client, PARENT_EMAIL)
        resp = client.delete(
            f"{PREFIX}/{other.id}/school-emails/{se.id}",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_delete_email_on_nonexistent_profile(self, client, setup):
        headers = _auth(client, PARENT_EMAIL)
        resp = client.delete(f"{PREFIX}/999999/school-emails/1", headers=headers)
        assert resp.status_code == 404

    def test_delete_wrong_profile_id_for_real_email(self, client, db_session, setup):
        """Email belongs to profile_a; using profile_b's id must 404."""
        from app.models.parent_gmail_integration import ParentChildSchoolEmail

        existing = (
            db_session.query(ParentChildSchoolEmail)
            .filter(ParentChildSchoolEmail.child_profile_id == setup["profile_a"].id)
            .first()
        )
        assert existing is not None

        headers = _auth(client, PARENT_EMAIL)
        resp = client.delete(
            f"{PREFIX}/{setup['profile_b'].id}/school-emails/{existing.id}",
            headers=headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# N+1 regression (#4049) — list_child_profiles eager-loads school_emails
# ---------------------------------------------------------------------------


class TestListProfilesQueryCount:
    def test_list_profiles_is_constant_query_count(self, client, db_session, setup):
        """Seed 5 profiles × 3 school emails (15 rows). The list endpoint
        must issue a constant number of SELECTs regardless of the N× factor —
        no N+1 on school_emails serialization."""
        from sqlalchemy import event
        from app.models.parent_gmail_integration import (
            ParentChildProfile,
            ParentChildSchoolEmail,
        )

        # Purge fixture profiles so we have an exactly-known 5×3 shape.
        db_session.query(ParentChildSchoolEmail).filter(
            ParentChildSchoolEmail.child_profile_id.in_(
                db_session.query(ParentChildProfile.id).filter(
                    ParentChildProfile.parent_id == setup["parent"].id,
                )
            )
        ).delete(synchronize_session=False)
        db_session.query(ParentChildProfile).filter(
            ParentChildProfile.parent_id == setup["parent"].id,
        ).delete()
        db_session.commit()

        profiles = []
        for i in range(5):
            p = ParentChildProfile(
                parent_id=setup["parent"].id,
                first_name=f"Kid{i}",
            )
            db_session.add(p)
            profiles.append(p)
        db_session.commit()
        for p in profiles:
            for j in range(3):
                db_session.add(ParentChildSchoolEmail(
                    child_profile_id=p.id,
                    email_address=f"kid{p.id}_{j}@school.ca",
                ))
        db_session.commit()

        # Count SELECTs on the shared engine during the request.
        engine = db_session.bind
        select_count = {"n": 0}

        def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if statement.strip().lower().startswith("select"):
                select_count["n"] += 1

        event.listen(engine, "before_cursor_execute", _before_cursor_execute)
        try:
            headers = _auth(client, PARENT_EMAIL)
            resp = client.get(PREFIX, headers=headers)
        finally:
            event.remove(engine, "before_cursor_execute", _before_cursor_execute)

        assert resp.status_code == 200
        data = resp.json()
        # 5 profiles, each with 3 school emails
        assert len(data) == 5
        total_emails = sum(len(p["school_emails"]) for p in data)
        assert total_emails == 15

        # With selectinload, school_emails should load in a single additional
        # SELECT — not one per profile. Bound generously (≤ 10) to absorb
        # auth + rate-limit + settings lookups, but catches true N+1 (would
        # be ≥ 5 extra selects for 5 profiles, easily pushing past 15).
        assert select_count["n"] <= 10, (
            f"list_child_profiles issued {select_count['n']} SELECTs for "
            f"5 profiles × 3 emails — likely N+1 on school_emails."
        )
