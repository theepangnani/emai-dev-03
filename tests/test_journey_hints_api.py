"""Tests for Journey Hints API endpoints (GET/POST /api/journey/hints/...)."""

import pytest
from conftest import PASSWORD, _auth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def parent_user(db_session):
    """Create a parent user for journey hint tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "jh_parent@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if user:
        return user

    user = User(
        email=email,
        full_name="Journey Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture()
def student_user(db_session):
    """Create a student user for journey hint tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = "jh_student@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if user:
        return user

    user = User(
        email=email,
        full_name="Journey Student",
        role=UserRole.STUDENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    return user


# ---------------------------------------------------------------------------
# Auth required
# ---------------------------------------------------------------------------

class TestJourneyHintsAuth:
    def test_get_hints_requires_auth(self, client):
        resp = client.get("/api/journey/hints")
        assert resp.status_code == 401

    def test_dismiss_requires_auth(self, client):
        resp = client.post("/api/journey/hints/link_your_child/dismiss")
        assert resp.status_code == 401

    def test_snooze_requires_auth(self, client):
        resp = client.post("/api/journey/hints/link_your_child/snooze")
        assert resp.status_code == 401

    def test_suppress_all_requires_auth(self, client):
        resp = client.post("/api/journey/hints/suppress-all")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/journey/hints
# ---------------------------------------------------------------------------

class TestGetHints:
    def test_returns_hint_for_parent(self, client, parent_user):
        headers = _auth(client, parent_user.email)
        resp = client.get("/api/journey/hints", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "hint" in data
        assert data["hint"] is not None
        assert data["hint"]["hint_key"] == "link_your_child"

    def test_returns_hint_with_page_filter(self, client, parent_user):
        headers = _auth(client, parent_user.email)
        resp = client.get("/api/journey/hints?page=dashboard", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["hint"] is not None
        assert data["hint"]["hint_key"] == "link_your_child"

    def test_returns_none_for_non_matching_page(self, client, parent_user):
        headers = _auth(client, parent_user.email)
        resp = client.get("/api/journey/hints?page=settings", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["hint"] is None

    def test_returns_hint_for_student(self, client, student_user):
        headers = _auth(client, student_user.email)
        resp = client.get("/api/journey/hints?page=dashboard", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["hint"] is not None
        assert data["hint"]["hint_key"] == "join_a_course"

    def test_hint_response_shape(self, client, parent_user):
        headers = _auth(client, parent_user.email)
        resp = client.get("/api/journey/hints", headers=headers)
        hint = resp.json()["hint"]
        assert "hint_key" in hint
        assert "title" in hint
        assert "description" in hint
        assert "journey_id" in hint
        assert "journey_url" in hint
        assert "diagram_url" in hint


# ---------------------------------------------------------------------------
# POST dismiss / snooze / suppress-all
# ---------------------------------------------------------------------------

class TestDismiss:
    def test_dismiss_hint(self, client, parent_user):
        headers = _auth(client, parent_user.email)
        resp = client.post("/api/journey/hints/link_your_child/dismiss", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "Hint dismissed"

    def test_dismissed_hint_no_longer_returned(self, client, parent_user):
        headers = _auth(client, parent_user.email)
        # Dismiss first
        client.post("/api/journey/hints/link_your_child/dismiss", headers=headers)
        # Now GET should not return it
        resp = client.get("/api/journey/hints?page=dashboard", headers=headers)
        data = resp.json()
        # Should be None since only one hint exists for parent on dashboard
        assert data["hint"] is None


class TestSnooze:
    def test_snooze_hint(self, client, student_user):
        headers = _auth(client, student_user.email)
        resp = client.post("/api/journey/hints/join_a_course/snooze", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "Hint snoozed for 7 days"

    def test_snoozed_hint_not_returned(self, client, student_user):
        headers = _auth(client, student_user.email)
        client.post("/api/journey/hints/join_a_course/snooze", headers=headers)
        resp = client.get("/api/journey/hints?page=dashboard", headers=headers)
        data = resp.json()
        assert data["hint"] is None


class TestSuppressAll:
    def test_suppress_all(self, client, parent_user):
        headers = _auth(client, parent_user.email)
        resp = client.post("/api/journey/hints/suppress-all", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "All hints suppressed"

    def test_suppressed_returns_no_hints(self, client, parent_user):
        headers = _auth(client, parent_user.email)
        client.post("/api/journey/hints/suppress-all", headers=headers)
        resp = client.get("/api/journey/hints", headers=headers)
        data = resp.json()
        assert data["hint"] is None
