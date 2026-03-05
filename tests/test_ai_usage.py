"""Tests for the AI Usage Limits feature (issue #1122).

Covers:
- GET /api/ai-usage — current user's AI usage stats
- POST /api/ai-usage/request — request more AI credits
- Admin CRUD on /api/admin/ai-usage
"""
import pytest
from conftest import PASSWORD, _auth


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture()
def users(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    admin_email = "aiu_admin@test.com"
    admin = db_session.query(User).filter(User.email == admin_email).first()
    if admin:
        student = db_session.query(User).filter(User.email == "aiu_student@test.com").first()
        parent = db_session.query(User).filter(User.email == "aiu_parent@test.com").first()
        return {"admin": admin, "student": student, "parent": parent}

    hashed = get_password_hash(PASSWORD)
    admin = User(email=admin_email, full_name="AIU Admin", role=UserRole.ADMIN, hashed_password=hashed)
    student = User(
        email="aiu_student@test.com", full_name="AIU Student", role=UserRole.STUDENT,
        hashed_password=hashed, ai_usage_count=5, ai_usage_limit=20,
    )
    parent = User(email="aiu_parent@test.com", full_name="AIU Parent", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([admin, student, parent])
    db_session.commit()
    for u in [admin, student, parent]:
        db_session.refresh(u)

    # Create student profile for the student user
    from app.models.student import Student
    s = db_session.query(Student).filter(Student.user_id == student.id).first()
    if not s:
        s = Student(user_id=student.id)
        db_session.add(s)
        db_session.commit()

    return {"admin": admin, "student": student, "parent": parent}


@pytest.fixture()
def maxed_out_user(db_session):
    """Create a user who has hit their AI usage limit."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student

    email = "aiu_maxed@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        hashed = get_password_hash(PASSWORD)
        user = User(
            email=email, full_name="Maxed User", role=UserRole.STUDENT,
            hashed_password=hashed, ai_usage_count=20, ai_usage_limit=20,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        s = Student(user_id=user.id)
        db_session.add(s)
        db_session.commit()
    else:
        user.ai_usage_count = 20
        user.ai_usage_limit = 20
        db_session.commit()

    return user


# ── User Endpoints ───────────────────────────────────────────

class TestGetAIUsage:
    def test_get_ai_usage(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/ai-usage/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "limit" in data
        assert "remaining" in data
        assert data["remaining"] == data["limit"] - data["count"]


class TestRequestCredits:
    def test_request_more_credits(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.post("/api/ai-usage/request", json={
            "requested_amount": 10,
            "reason": "Need more for studying",
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["requested_amount"] == 10

    def test_request_invalid_amount(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.post("/api/ai-usage/request", json={
            "requested_amount": 0,
            "reason": "Invalid",
        }, headers=headers)
        assert resp.status_code == 422

        resp2 = client.post("/api/ai-usage/request", json={
            "requested_amount": -5,
            "reason": "Negative",
        }, headers=headers)
        assert resp2.status_code == 422


# ── Admin Endpoints ──────────────────────────────────────────

class TestAdminAIUsage:
    def test_admin_list_usage(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_admin_list_requests(self, client, users):
        # First create a credit request
        student_headers = _auth(client, users["student"].email)
        client.post("/api/ai-usage/request", json={
            "requested_amount": 5,
            "reason": "Admin list test",
        }, headers=student_headers)

        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage/requests", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_admin_approve_request(self, client, users, db_session):
        from app.models.ai_limit_request import AILimitRequest

        # Create a pending request directly
        req = AILimitRequest(
            user_id=users["student"].id,
            requested_amount=15,
            reason="Approve test",
            status="pending",
        )
        db_session.add(req)
        db_session.commit()
        db_session.refresh(req)

        old_limit = users["student"].ai_usage_limit or 10
        headers = _auth(client, users["admin"].email)
        resp = client.patch(f"/api/admin/ai-usage/requests/{req.id}/approve", json={
            "approved_amount": 15,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"

        # Verify limit was increased
        db_session.refresh(users["student"])
        assert users["student"].ai_usage_limit >= old_limit + 15

    def test_admin_decline_request(self, client, users, db_session):
        from app.models.ai_limit_request import AILimitRequest

        req = AILimitRequest(
            user_id=users["student"].id,
            requested_amount=10,
            reason="Decline test",
            status="pending",
        )
        db_session.add(req)
        db_session.commit()
        db_session.refresh(req)

        headers = _auth(client, users["admin"].email)
        resp = client.patch(f"/api/admin/ai-usage/requests/{req.id}/decline", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "declined"

    def test_admin_set_user_limit(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.patch(
            f"/api/admin/ai-usage/users/{users['student'].id}/limit",
            json={"ai_usage_limit": 50},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_usage_limit"] == 50

    def test_admin_reset_count(self, client, users, db_session):
        # Ensure there's a non-zero count
        users["student"].ai_usage_count = 10
        db_session.commit()

        headers = _auth(client, users["admin"].email)
        resp = client.post(
            f"/api/admin/ai-usage/users/{users['student'].id}/reset",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ai_usage_count"] == 0
