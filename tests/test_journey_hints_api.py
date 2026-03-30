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
    from app.models.journey_hint import JourneyHint

    email = "jh_parent@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name="Journey Parent",
            role=UserRole.PARENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(user)
        db_session.flush()

    # Clean prior hints so welcome_modal fires
    db_session.query(JourneyHint).filter(JourneyHint.user_id == user.id).delete()
    db_session.commit()
    return user


@pytest.fixture()
def student_user(db_session):
    """Create a student user for journey hint tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.journey_hint import JourneyHint

    email = "jh_student@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name="Journey Student",
            role=UserRole.STUDENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(user)
        db_session.flush()

    # Clean prior hints
    db_session.query(JourneyHint).filter(JourneyHint.user_id == user.id).delete()
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
        resp = client.post("/api/journey/hints/parent.add_child/dismiss")
        assert resp.status_code == 401

    def test_snooze_requires_auth(self, client):
        resp = client.post("/api/journey/hints/parent.add_child/snooze")
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
        # First hint for a brand-new user is welcome_modal
        assert data["hint"]["hint_key"] == "welcome_modal"

    def test_returns_hint_with_page_filter(self, client, parent_user):
        headers = _auth(client, parent_user.email)
        # welcome_modal has pages=None (any page), so dashboard works
        resp = client.get("/api/journey/hints?page=dashboard", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["hint"] is not None

    def test_returns_none_for_non_matching_page(self, client, parent_user, db_session):
        """After dismissing welcome_modal, page-specific hints apply."""
        from app.models.journey_hint import JourneyHint
        # Dismiss welcome_modal so page-specific hints are checked
        db_session.add(JourneyHint(
            user_id=parent_user.id, hint_key="welcome_modal", status="dismissed",
        ))
        # Dismiss add_child too
        db_session.add(JourneyHint(
            user_id=parent_user.id, hint_key="parent.add_child", status="dismissed",
        ))
        db_session.commit()

        headers = _auth(client, parent_user.email)
        # settings page has no matching hints for parent (after welcome + add_child dismissed)
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
        # First hint is welcome_modal for any new user
        assert data["hint"]["hint_key"] == "welcome_modal"

    def test_hint_response_shape(self, client, parent_user):
        headers = _auth(client, parent_user.email)
        resp = client.get("/api/journey/hints", headers=headers)
        hint = resp.json()["hint"]
        assert hint is not None
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
        resp = client.post("/api/journey/hints/parent.add_child/dismiss", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "Hint dismissed"

    def test_dismissed_hint_no_longer_returned(self, client, parent_user, db_session):
        from app.models.journey_hint import JourneyHint
        headers = _auth(client, parent_user.email)
        # Dismiss welcome_modal first
        client.post("/api/journey/hints/welcome_modal/dismiss", headers=headers)
        # Dismiss parent.add_child
        client.post("/api/journey/hints/parent.add_child/dismiss", headers=headers)
        # GET on my-kids page — add_child is dismissed, so should get next or None
        resp = client.get("/api/journey/hints?page=my-kids", headers=headers)
        data = resp.json()
        # If a hint is returned, it should NOT be the dismissed ones
        if data["hint"]:
            assert data["hint"]["hint_key"] not in ("welcome_modal", "parent.add_child")


class TestSnooze:
    def test_snooze_hint(self, client, student_user):
        headers = _auth(client, student_user.email)
        resp = client.post("/api/journey/hints/student.first_guide/snooze", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["message"] == "Hint snoozed for 7 days"


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

    def test_suppress_all_not_routed_to_dismiss(self, client, parent_user):
        """Regression: suppress-all must not match {hint_key}='suppress-all' (#2628)."""
        headers = _auth(client, parent_user.email)
        resp = client.post("/api/journey/hints/suppress-all", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # If routed to dismiss, message would be "Hint dismissed"
        assert data["message"] != "Hint dismissed"
        assert data["message"] == "All hints suppressed"
