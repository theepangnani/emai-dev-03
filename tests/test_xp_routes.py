"""Tests for XP / Gamification API routes."""
import pytest
from unittest.mock import patch

from conftest import PASSWORD, _auth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def xp_users(db_session):
    """Create a parent, child (student), and teacher for XP tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students

    hashed = get_password_hash(PASSWORD)

    # Reuse existing rows if already created (session-scoped DB)
    parent = db_session.query(User).filter(User.email == "xpparent@test.com").first()
    if parent:
        child_user = db_session.query(User).filter(User.email == "xpchild@test.com").first()
        student = db_session.query(Student).filter(Student.user_id == child_user.id).first()
        teacher = db_session.query(User).filter(User.email == "xpteacher@test.com").first()
        outsider = db_session.query(User).filter(User.email == "xpoutsider@test.com").first()
        return {
            "parent": parent,
            "child_user": child_user,
            "student": student,
            "teacher": teacher,
            "outsider": outsider,
        }

    parent = User(email="xpparent@test.com", full_name="XP Parent", role=UserRole.PARENT, hashed_password=hashed)
    child_user = User(email="xpchild@test.com", full_name="XP Child", role=UserRole.STUDENT, hashed_password=hashed)
    teacher = User(email="xpteacher@test.com", full_name="XP Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    outsider = User(email="xpoutsider@test.com", full_name="XP Outsider", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([parent, child_user, teacher, outsider])
    db_session.commit()

    student = Student(user_id=child_user.id, grade_level=8)
    db_session.add(student)
    db_session.commit()

    # Link parent to child
    db_session.execute(parent_students.insert().values(parent_id=parent.id, student_id=student.id))
    db_session.commit()

    return {
        "parent": parent,
        "child_user": child_user,
        "student": student,
        "teacher": teacher,
        "outsider": outsider,
    }


# ---------------------------------------------------------------------------
# GET /api/xp/summary
# ---------------------------------------------------------------------------

def test_get_xp_summary(client, xp_users):
    headers = _auth(client, "xpchild@test.com")
    resp = client.get("/api/xp/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_xp" in data
    assert "current_level" in data
    assert "level_title" in data
    assert "current_streak" in data
    assert "freeze_tokens_remaining" in data
    assert "xp_to_next_level" in data
    assert "today_xp" in data
    assert "today_cap" in data


def test_get_xp_summary_unauthenticated(client):
    resp = client.get("/api/xp/summary")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/xp/history
# ---------------------------------------------------------------------------

def test_get_xp_history(client, xp_users):
    headers = _auth(client, "xpchild@test.com")
    resp = client.get("/api/xp/history", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_get_xp_history_with_pagination(client, xp_users):
    headers = _auth(client, "xpchild@test.com")
    resp = client.get("/api/xp/history?limit=10&offset=5", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


# ---------------------------------------------------------------------------
# GET /api/xp/badges
# ---------------------------------------------------------------------------

def test_get_badges(client, xp_users):
    headers = _auth(client, "xpchild@test.com")
    resp = client.get("/api/xp/badges", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# GET /api/xp/streak
# ---------------------------------------------------------------------------

def test_get_streak(client, xp_users):
    headers = _auth(client, "xpchild@test.com")
    resp = client.get("/api/xp/streak", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "current_streak" in data
    assert "longest_streak" in data


# ---------------------------------------------------------------------------
# POST /api/xp/award (brownie points)
# ---------------------------------------------------------------------------

def test_award_brownie_points_parent(client, xp_users):
    """Parent awards brownie points to their child."""
    headers = _auth(client, "xpparent@test.com")
    resp = client.post("/api/xp/award", json={
        "student_user_id": xp_users["child_user"].id,
        "points": 10,
        "reason": "Great job on homework",
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["awarded"] == 10
    assert data["student_user_id"] == xp_users["child_user"].id


def test_award_brownie_points_teacher(client, xp_users):
    """Teacher can award brownie points to any student."""
    headers = _auth(client, "xpteacher@test.com")
    resp = client.post("/api/xp/award", json={
        "student_user_id": xp_users["child_user"].id,
        "points": 5,
        "reason": "Excellent participation",
    }, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["awarded"] == 5


def test_award_brownie_points_outsider_forbidden(client, xp_users):
    """Parent cannot award points to a child that is not theirs."""
    headers = _auth(client, "xpoutsider@test.com")
    resp = client.post("/api/xp/award", json={
        "student_user_id": xp_users["child_user"].id,
        "points": 10,
    }, headers=headers)
    assert resp.status_code == 403


def test_award_brownie_points_student_forbidden(client, xp_users):
    """Students cannot award brownie points."""
    headers = _auth(client, "xpchild@test.com")
    resp = client.post("/api/xp/award", json={
        "student_user_id": xp_users["child_user"].id,
        "points": 10,
    }, headers=headers)
    assert resp.status_code == 403


def test_award_brownie_points_invalid_points(client, xp_users):
    """Points must be between 1 and 50."""
    headers = _auth(client, "xpparent@test.com")
    resp = client.post("/api/xp/award", json={
        "student_user_id": xp_users["child_user"].id,
        "points": 100,
    }, headers=headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/xp/children/{student_id}/summary (parent view)
# ---------------------------------------------------------------------------

def test_parent_views_child_xp(client, xp_users):
    headers = _auth(client, "xpparent@test.com")
    resp = client.get(f"/api/xp/children/{xp_users['student'].id}/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "current_level" in data
    assert "total_xp" in data


def test_outsider_cannot_view_child_xp(client, xp_users):
    """A parent who is NOT linked cannot view the child's XP."""
    headers = _auth(client, "xpoutsider@test.com")
    resp = client.get(f"/api/xp/children/{xp_users['student'].id}/summary", headers=headers)
    assert resp.status_code == 403


def test_student_cannot_view_child_endpoint(client, xp_users):
    """Students cannot use the parent child-view endpoint."""
    headers = _auth(client, "xpchild@test.com")
    resp = client.get(f"/api/xp/children/{xp_users['student'].id}/summary", headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# XP hook: award_xp is non-blocking (study.py, quiz_results.py, etc.)
# ---------------------------------------------------------------------------

def test_xp_award_stub_does_not_raise(db_session, xp_users):
    """Verify the XpService stub works without raising."""
    from app.services.xp_service import XpService
    # Should not raise even though there are no XP tables yet
    XpService.award_xp(db_session, xp_users["child_user"].id, "study_guide")
    XpService.award_xp(db_session, xp_users["child_user"].id, "quiz_complete")
    XpService.award_xp(db_session, xp_users["child_user"].id, "flashcard_deck")
    XpService.award_xp(db_session, xp_users["child_user"].id, "upload")


def test_xp_feature_flag_disabled(db_session, xp_users):
    """When XP_ENABLED=false, award_xp returns None immediately."""
    from app.services.xp_service import XpService
    from app.core.config import settings

    original = settings.xp_enabled
    try:
        settings.xp_enabled = False
        result = XpService.award_xp(db_session, xp_users["child_user"].id, "study_guide")
        assert result is None
    finally:
        settings.xp_enabled = original
