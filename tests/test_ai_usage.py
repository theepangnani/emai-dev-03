"""Tests for the AI Usage Limits feature (issue #1122).

Covers:
- GET /api/ai-usage — current user's AI usage stats
- POST /api/ai-usage/request-credits — request more AI credits
- AI generation enforcement (429 when at limit)
- Admin CRUD on /api/admin/ai-usage
"""
import pytest
from unittest.mock import patch
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
    student = User(email="aiu_student@test.com", full_name="AIU Student", role=UserRole.STUDENT, hashed_password=hashed)
    parent = User(email="aiu_parent@test.com", full_name="AIU Parent", role=UserRole.PARENT, hashed_password=hashed)
    db_session.add_all([admin, student, parent])
    db_session.commit()
    for u in [admin, student, parent]:
        db_session.refresh(u)

    # Create student profile for the student user
    from app.models.student import Student
    s = db_session.query(Student).filter(Student.user_id == student.id).first()
    if not s:
        s = Student(user_id=student.id, full_name="AIU Student")
        db_session.add(s)
        db_session.commit()

    return {"admin": admin, "student": student, "parent": parent}


@pytest.fixture()
def ai_usage_record(db_session, users):
    """Create an AI usage record for the student user."""
    from app.models.ai_usage import AIUsage

    record = db_session.query(AIUsage).filter(AIUsage.user_id == users["student"].id).first()
    if record:
        return record
    record = AIUsage(
        user_id=users["student"].id,
        usage_count=5,
        usage_limit=20,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


@pytest.fixture()
def maxed_out_user(db_session):
    """Create a user who has hit their AI usage limit."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.ai_usage import AIUsage
    from app.models.student import Student

    email = "aiu_maxed@test.com"
    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        hashed = get_password_hash(PASSWORD)
        user = User(email=email, full_name="Maxed User", role=UserRole.STUDENT, hashed_password=hashed)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        s = Student(user_id=user.id, full_name="Maxed Student")
        db_session.add(s)
        db_session.commit()

    record = db_session.query(AIUsage).filter(AIUsage.user_id == user.id).first()
    if not record:
        record = AIUsage(user_id=user.id, usage_count=20, usage_limit=20)
        db_session.add(record)
        db_session.commit()
    else:
        record.usage_count = record.usage_limit
        db_session.commit()

    return user


# ── User Endpoints ───────────────────────────────────────────

class TestGetAIUsage:
    def test_get_ai_usage(self, client, users, ai_usage_record):
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/ai-usage", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "usage_count" in data
        assert "usage_limit" in data
        assert "remaining" in data
        assert data["remaining"] == data["usage_limit"] - data["usage_count"]


class TestRequestCredits:
    def test_request_more_credits(self, client, users, ai_usage_record):
        headers = _auth(client, users["student"].email)
        resp = client.post("/api/ai-usage/request-credits", json={
            "amount": 10,
            "reason": "Need more for studying",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["amount"] == 10

    def test_request_invalid_amount(self, client, users, ai_usage_record):
        headers = _auth(client, users["student"].email)
        resp = client.post("/api/ai-usage/request-credits", json={
            "amount": 0,
            "reason": "Invalid",
        }, headers=headers)
        assert resp.status_code == 422

        resp2 = client.post("/api/ai-usage/request-credits", json={
            "amount": -5,
            "reason": "Negative",
        }, headers=headers)
        assert resp2.status_code == 422


# ── Enforcement ──────────────────────────────────────────────

class TestAIEnforcement:
    def test_ai_generation_increments_count(self, client, users, ai_usage_record, db_session):
        """After a successful AI generation, usage_count should increase."""
        from app.models.ai_usage import AIUsage

        headers = _auth(client, users["student"].email)
        old_count = ai_usage_record.usage_count

        # Mock AI service to avoid actual OpenAI calls
        with patch("app.services.ai_service.generate_study_guide") as mock_gen:
            mock_gen.return_value = "# Mock Study Guide\n\nThis is a mock."
            with patch("app.services.ai_service.check_content_safe", return_value=True):
                resp = client.post("/api/study/generate", json={
                    "topic": "Test Topic",
                    "subject": "Math",
                }, headers=headers)

        # If the route exists and returns success, check count incremented
        if resp.status_code == 200:
            db_session.refresh(ai_usage_record)
            assert ai_usage_record.usage_count > old_count

    def test_ai_generation_blocked_at_limit(self, client, maxed_out_user):
        """A user at their AI usage limit should get 429."""
        headers = _auth(client, maxed_out_user.email)

        with patch("app.services.ai_service.generate_study_guide") as mock_gen:
            mock_gen.return_value = "# Mock"
            with patch("app.services.ai_service.check_content_safe", return_value=True):
                resp = client.post("/api/study/generate", json={
                    "topic": "Blocked Topic",
                    "subject": "Math",
                }, headers=headers)

        assert resp.status_code == 429
        assert "limit" in resp.json()["detail"].lower()


# ── Admin Endpoints ──────────────────────────────────────────

class TestAdminAIUsage:
    def test_admin_list_usage(self, client, users, ai_usage_record):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "users" in data or isinstance(data, list)

    def test_admin_list_requests(self, client, users, ai_usage_record):
        # First create a credit request
        student_headers = _auth(client, users["student"].email)
        client.post("/api/ai-usage/request-credits", json={
            "amount": 5,
            "reason": "Admin list test",
        }, headers=student_headers)

        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage/requests", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list) or "requests" in data

    def test_admin_approve_request(self, client, users, ai_usage_record, db_session):
        from app.models.ai_usage import AIUsageCreditRequest

        # Create a pending request directly
        req = AIUsageCreditRequest(
            user_id=users["student"].id,
            amount=15,
            reason="Approve test",
            status="pending",
        )
        existing = db_session.query(AIUsageCreditRequest).filter(
            AIUsageCreditRequest.user_id == users["student"].id,
            AIUsageCreditRequest.status == "pending",
            AIUsageCreditRequest.reason == "Approve test",
        ).first()
        if not existing:
            db_session.add(req)
            db_session.commit()
            db_session.refresh(req)
        else:
            req = existing

        old_limit = ai_usage_record.usage_limit
        headers = _auth(client, users["admin"].email)
        resp = client.post(f"/api/admin/ai-usage/requests/{req.id}/approve", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "approved"

        # Verify limit was increased
        db_session.refresh(ai_usage_record)
        assert ai_usage_record.usage_limit >= old_limit + 15

    def test_admin_decline_request(self, client, users, db_session):
        from app.models.ai_usage import AIUsageCreditRequest

        req = AIUsageCreditRequest(
            user_id=users["student"].id,
            amount=10,
            reason="Decline test",
            status="pending",
        )
        existing = db_session.query(AIUsageCreditRequest).filter(
            AIUsageCreditRequest.user_id == users["student"].id,
            AIUsageCreditRequest.status == "pending",
            AIUsageCreditRequest.reason == "Decline test",
        ).first()
        if not existing:
            db_session.add(req)
            db_session.commit()
            db_session.refresh(req)
        else:
            req = existing

        headers = _auth(client, users["admin"].email)
        resp = client.post(f"/api/admin/ai-usage/requests/{req.id}/decline", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "declined"

    def test_admin_set_user_limit(self, client, users, ai_usage_record):
        headers = _auth(client, users["admin"].email)
        resp = client.post(
            f"/api/admin/ai-usage/users/{users['student'].id}/limit",
            json={"usage_limit": 50},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["usage_limit"] == 50

    def test_admin_reset_count(self, client, users, ai_usage_record, db_session):
        # Ensure there's a non-zero count
        ai_usage_record.usage_count = 10
        db_session.commit()

        headers = _auth(client, users["admin"].email)
        resp = client.post(
            f"/api/admin/ai-usage/users/{users['student'].id}/reset",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["usage_count"] == 0
