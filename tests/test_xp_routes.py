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
# GET /api/xp/summary — #4019 XpStreakBadge fields (xp_total, streak_days)
# ---------------------------------------------------------------------------

def test_xp_summary_zero_state(client, db_session, xp_users):
    """Authenticated user with no ledger entries returns xp_total=0, streak_days=0."""
    from app.models.xp import XpLedger, XpSummary

    # Clean state for a brand-new summary user.
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    hashed = get_password_hash(PASSWORD)
    fresh = db_session.query(User).filter(User.email == "xpfresh@test.com").first()
    if not fresh:
        fresh = User(
            email="xpfresh@test.com",
            full_name="Fresh Kid",
            role=UserRole.STUDENT,
            hashed_password=hashed,
        )
        db_session.add(fresh)
        db_session.commit()

    # Make absolutely sure there's no prior ledger/summary for this user.
    db_session.query(XpLedger).filter(XpLedger.student_id == fresh.id).delete()
    db_session.query(XpSummary).filter(XpSummary.student_id == fresh.id).delete()
    db_session.commit()

    headers = _auth(client, "xpfresh@test.com")
    resp = client.get("/api/xp/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["xp_total"] == 0
    assert data["streak_days"] == 0


def test_xp_summary_returns_xp_total_and_streak_days(
    client, db_session, xp_users,
):
    """After an XP award, xp_total mirrors total_xp and streak_days mirrors current_streak."""
    from app.services.xp_service import XpService
    from app.models.xp import XpLedger, XpSummary

    child_id = xp_users["child_user"].id

    # Clean slate, then award a single XP event.
    db_session.query(XpLedger).filter(XpLedger.student_id == child_id).delete()
    db_session.query(XpSummary).filter(XpSummary.student_id == child_id).delete()
    db_session.commit()

    entry = XpService.award_xp(db_session, child_id, "ile_session_complete")
    assert entry is not None  # guard: the award shouldn't be suppressed
    db_session.commit()

    headers = _auth(client, "xpchild@test.com")
    resp = client.get("/api/xp/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    # xp_total is an alias of total_xp (#4019, #4029 computed_field)
    assert data["xp_total"] == data["total_xp"]
    assert data["xp_total"] >= 1

    # streak_days mirrors current_streak (#4019)
    assert data["streak_days"] == data["current_streak"]

    # #4029: The schema must not carry two duplicate Python fields for
    # total_xp. Verify by introspecting model_fields (computed_field is
    # excluded from this dict, duplicate-declared fields would not be).
    from app.schemas.xp import XpSummaryResponse
    assert "total_xp" in XpSummaryResponse.model_fields
    assert "xp_total" not in XpSummaryResponse.model_fields


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


def test_award_brownie_points_teacher(client, xp_users, db_session):
    """Teacher can award brownie points to a linked student."""
    from app.models.student import Student, student_teachers

    # Link teacher to student
    student = db_session.query(Student).filter(Student.user_id == xp_users["child_user"].id).first()
    existing = db_session.query(student_teachers).filter(
        student_teachers.c.student_id == student.id,
        student_teachers.c.teacher_user_id == xp_users["teacher"].id,
    ).first()
    if not existing:
        db_session.execute(student_teachers.insert().values(
            student_id=student.id,
            teacher_user_id=xp_users["teacher"].id,
            teacher_name="XP Teacher",
            teacher_email="xpteacher@test.com",
        ))
        db_session.commit()

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


# ---------------------------------------------------------------------------
# Brownie points: ledger entry creation (#2005)
# ---------------------------------------------------------------------------

def test_brownie_award_creates_ledger_entry(db_session, xp_users):
    """Award creates a ledger entry with correct fields."""
    from app.models.xp import XpLedger

    headers_parent = xp_users["parent"]  # we use service directly
    from app.services.xp_service import XpService

    result = XpService.award_brownie_points(
        db_session,
        student_user_id=xp_users["child_user"].id,
        points=7,
        awarder_id=xp_users["parent"].id,
        reason="Test reason",
        weekly_cap=50,
    )
    db_session.commit()

    assert result.awarded == 7
    assert result.student_user_id == xp_users["child_user"].id

    entry = (
        db_session.query(XpLedger)
        .filter(
            XpLedger.student_id == xp_users["child_user"].id,
            XpLedger.action_type == "brownie_points",
            XpLedger.awarder_id == xp_users["parent"].id,
        )
        .order_by(XpLedger.created_at.desc())
        .first()
    )
    assert entry is not None
    assert entry.xp_awarded == 7
    assert entry.reason == "Test reason"


# ---------------------------------------------------------------------------
# Brownie points: weekly cap enforcement (#2005)
# ---------------------------------------------------------------------------

def test_brownie_weekly_cap_parent(client, db_session, xp_users):
    """Parent is capped at 50 XP/week per child."""
    from app.models.xp import XpLedger
    from datetime import datetime, timezone

    headers = _auth(client, "xpparent@test.com")

    # Clean up any old brownie entries for a clean test
    db_session.query(XpLedger).filter(
        XpLedger.awarder_id == xp_users["parent"].id,
        XpLedger.student_id == xp_users["child_user"].id,
        XpLedger.action_type == "brownie_points",
    ).delete()
    db_session.commit()

    # Award 50 XP in one shot
    resp = client.post("/api/xp/award", json={
        "student_user_id": xp_users["child_user"].id,
        "points": 50,
        "reason": "Cap test",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["awarded"] == 50

    # Next award should be rejected (cap exceeded)
    resp2 = client.post("/api/xp/award", json={
        "student_user_id": xp_users["child_user"].id,
        "points": 1,
    }, headers=headers)
    assert resp2.status_code == 400
    assert "cap" in resp2.json()["detail"].lower() or "reached" in resp2.json()["detail"].lower()


def test_brownie_weekly_cap_teacher(client, db_session, xp_users):
    """Teacher is capped at 30 XP/week per student."""
    from app.models.xp import XpLedger
    from app.models.student import Student, student_teachers

    headers = _auth(client, "xpteacher@test.com")

    # Link teacher to student
    student = db_session.query(Student).filter(Student.user_id == xp_users["child_user"].id).first()
    existing_link = db_session.query(student_teachers).filter(
        student_teachers.c.student_id == student.id,
        student_teachers.c.teacher_user_id == xp_users["teacher"].id,
    ).first()
    if not existing_link:
        db_session.execute(student_teachers.insert().values(
            student_id=student.id,
            teacher_user_id=xp_users["teacher"].id,
            teacher_name="XP Teacher",
            teacher_email="xpteacher@test.com",
        ))
        db_session.commit()

    # Clean up any old brownie entries
    db_session.query(XpLedger).filter(
        XpLedger.awarder_id == xp_users["teacher"].id,
        XpLedger.student_id == xp_users["child_user"].id,
        XpLedger.action_type == "brownie_points",
    ).delete()
    db_session.commit()

    # Award 30 XP
    resp = client.post("/api/xp/award", json={
        "student_user_id": xp_users["child_user"].id,
        "points": 30,
        "reason": "Teacher cap test",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["awarded"] == 30

    # Next award should be rejected
    resp2 = client.post("/api/xp/award", json={
        "student_user_id": xp_users["child_user"].id,
        "points": 1,
    }, headers=headers)
    assert resp2.status_code == 400


# ---------------------------------------------------------------------------
# Brownie points: non-related user blocked (#2005)
# ---------------------------------------------------------------------------

def test_brownie_unlinked_teacher_blocked(client, db_session, xp_users):
    """Teacher who is NOT linked to a student cannot award points."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    # Create an unlinked teacher
    hashed = get_password_hash(PASSWORD)
    unlinked = db_session.query(User).filter(User.email == "xpunlinked_teacher@test.com").first()
    if not unlinked:
        unlinked = User(email="xpunlinked_teacher@test.com", full_name="Unlinked Teacher",
                        role=UserRole.TEACHER, hashed_password=hashed)
        db_session.add(unlinked)
        db_session.commit()

    headers = _auth(client, "xpunlinked_teacher@test.com")
    resp = client.post("/api/xp/award", json={
        "student_user_id": xp_users["child_user"].id,
        "points": 5,
    }, headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Admin audit endpoint (#2005)
# ---------------------------------------------------------------------------

def test_admin_xp_awards_endpoint(client, db_session, xp_users):
    """Admin can list brownie point awards."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    hashed = get_password_hash(PASSWORD)
    admin = db_session.query(User).filter(User.email == "xpadmin@test.com").first()
    if not admin:
        admin = User(email="xpadmin@test.com", full_name="XP Admin",
                     role=UserRole.ADMIN, hashed_password=hashed)
        db_session.add(admin)
        db_session.commit()

    headers = _auth(client, "xpadmin@test.com")
    resp = client.get("/api/admin/xp-awards", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_admin_xp_awards_filter_by_awarder(client, db_session, xp_users):
    """Admin can filter XP awards by awarder_id."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    hashed = get_password_hash(PASSWORD)
    admin = db_session.query(User).filter(User.email == "xpadmin@test.com").first()
    if not admin:
        admin = User(email="xpadmin@test.com", full_name="XP Admin",
                     role=UserRole.ADMIN, hashed_password=hashed)
        db_session.add(admin)
        db_session.commit()

    headers = _auth(client, "xpadmin@test.com")
    resp = client.get(f"/api/admin/xp-awards?awarder_id={xp_users['parent'].id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["awarder_id"] == xp_users["parent"].id


def test_non_admin_cannot_access_xp_awards(client, xp_users):
    """Non-admin users cannot access the XP audit endpoint."""
    headers = _auth(client, "xpparent@test.com")
    resp = client.get("/api/admin/xp-awards", headers=headers)
    assert resp.status_code == 403
