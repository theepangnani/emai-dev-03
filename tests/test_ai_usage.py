"""Tests for the AI Usage Limits feature (issue #1122) and audit log (#1125).

Covers:
- GET /api/ai-usage — current user's AI usage stats
- POST /api/ai-usage/request — request more AI credits
- GET /api/ai-usage/history — user's own usage history
- Admin CRUD on /api/admin/ai-usage
- GET /api/admin/ai-usage/history — admin usage audit log
- GET /api/admin/ai-usage/requests — all requests (not just pending)
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
        resp = client.get("/api/ai-usage", headers=headers)
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
        resp = client.get("/api/admin/ai-usage", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data and "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

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
        assert "items" in data and "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

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

    def test_admin_list_requests_all_statuses(self, client, users, db_session):
        """GET /api/admin/ai-usage/requests defaults to 'all' and returns all statuses."""
        from app.models.ai_limit_request import AILimitRequest

        # Create requests in different statuses
        for status_val in ("pending", "approved", "declined"):
            req = AILimitRequest(
                user_id=users["student"].id,
                requested_amount=5,
                reason=f"Test {status_val}",
                status=status_val,
            )
            db_session.add(req)
        db_session.commit()

        headers = _auth(client, users["admin"].email)
        # No status filter — should return all
        resp = client.get("/api/admin/ai-usage/requests", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data and "total" in data
        statuses = {r["status"] for r in data["items"]}
        # Should include more than just pending
        assert len(statuses) >= 2

    def test_admin_list_requests_filter_pending(self, client, users, db_session):
        """GET /api/admin/ai-usage/requests?status=pending returns only pending."""
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage/requests?status=pending", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data and "total" in data
        for r in data["items"]:
            assert r["status"] == "pending"


# ── Usage History Endpoints ─────────────────────────────────

class TestAIUsageHistory:
    def _seed_history(self, db_session, user_id, count=3):
        """Seed ai_usage_history rows for a user."""
        from app.models.ai_usage_history import AIUsageHistory
        for i, gen_type in enumerate(["study_guide", "quiz", "flashcards"]):
            if i >= count:
                break
            entry = AIUsageHistory(
                user_id=user_id,
                generation_type=gen_type,
                credits_used=1,
            )
            db_session.add(entry)
        db_session.commit()

    def test_user_history_empty(self, client, users):
        """New users should get empty history."""
        headers = _auth(client, users["parent"].email)
        resp = client.get("/api/ai-usage/history", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 0
        assert isinstance(data["items"], list)

    def test_user_history_returns_own(self, client, users, db_session):
        """User sees their own history entries."""
        self._seed_history(db_session, users["student"].id)
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/ai-usage/history", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        for item in data["items"]:
            assert item["user_id"] == users["student"].id

    def test_user_history_filter_type(self, client, users, db_session):
        """User can filter history by generation type."""
        self._seed_history(db_session, users["student"].id)
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/ai-usage/history?generation_type=quiz", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["generation_type"] == "quiz"

    def test_user_history_requires_auth(self, client):
        """History endpoint requires authentication."""
        resp = client.get("/api/ai-usage/history")
        assert resp.status_code in (401, 403)

    def test_admin_history(self, client, users, db_session):
        """Admin can see all users' history."""
        self._seed_history(db_session, users["student"].id)
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage/history", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        assert isinstance(data["items"], list)
        # Check enrichment fields
        for item in data["items"]:
            assert "user_name" in item
            assert "user_email" in item
            assert "generation_type" in item

    def test_admin_history_filter_type(self, client, users, db_session):
        """Admin can filter history by generation type."""
        self._seed_history(db_session, users["student"].id)
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage/history?generation_type=study_guide", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["generation_type"] == "study_guide"

    def test_admin_history_filter_user(self, client, users, db_session):
        """Admin can filter history by user_id."""
        self._seed_history(db_session, users["student"].id)
        headers = _auth(client, users["admin"].email)
        resp = client.get(
            f"/api/admin/ai-usage/history?user_id={users['student'].id}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["user_id"] == users["student"].id

    def test_admin_history_search(self, client, users, db_session):
        """Admin can search history by user name."""
        self._seed_history(db_session, users["student"].id)
        headers = _auth(client, users["admin"].email)
        resp = client.get(
            "/api/admin/ai-usage/history?search=AIU Student",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_admin_history_requires_admin(self, client, users):
        """Non-admin users cannot access admin history."""
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/admin/ai-usage/history", headers=headers)
        assert resp.status_code == 403

    def test_log_ai_usage_creates_entry(self, db_session, users):
        """log_ai_usage inserts a row into ai_usage_history."""
        from app.services.ai_usage import log_ai_usage
        from app.models.ai_usage_history import AIUsageHistory

        before = db_session.query(AIUsageHistory).filter(
            AIUsageHistory.user_id == users["student"].id
        ).count()

        log_ai_usage(users["student"], db_session, "quiz", course_material_id=None, credits_used=1)
        db_session.commit()

        after = db_session.query(AIUsageHistory).filter(
            AIUsageHistory.user_id == users["student"].id
        ).count()

        assert after == before + 1


# ── UTDF: check_ai_usage cost parameter tests (S15 #2961) ────

class TestCheckAIUsageCost:
    """Test the cost parameter on check_ai_usage."""

    def test_check_ai_usage_default_cost(self, db_session):
        """Default cost=1 should work for users with remaining credits."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.services.ai_usage import check_ai_usage

        email = "aiu_cost_default@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            hashed = get_password_hash(PASSWORD)
            user = User(
                email=email, full_name="Cost Default User", role=UserRole.STUDENT,
                hashed_password=hashed, ai_usage_count=5, ai_usage_limit=20,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)

        # Should not raise — 5 used of 20, default cost=1 is fine
        check_ai_usage(user, db_session)

    def test_check_ai_usage_cost_2(self, db_session):
        """1 remaining credit + cost=2 should raise 429."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.services.ai_usage import check_ai_usage
        from fastapi import HTTPException

        email = "aiu_cost_2@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            hashed = get_password_hash(PASSWORD)
            user = User(
                email=email, full_name="Cost 2 User", role=UserRole.STUDENT,
                hashed_password=hashed, ai_usage_count=19, ai_usage_limit=20,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
        else:
            user.ai_usage_count = 19
            user.ai_usage_limit = 20
            db_session.commit()

        # 1 remaining, cost=2 should fail
        with pytest.raises(HTTPException) as exc_info:
            check_ai_usage(user, db_session, cost=2)
        assert exc_info.value.status_code == 429

    def test_check_ai_usage_cost_0(self, db_session):
        """Cost=0 (free action) should always pass, even at limit."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole
        from app.services.ai_usage import check_ai_usage

        email = "aiu_cost_0@test.com"
        user = db_session.query(User).filter(User.email == email).first()
        if not user:
            hashed = get_password_hash(PASSWORD)
            user = User(
                email=email, full_name="Cost 0 User", role=UserRole.STUDENT,
                hashed_password=hashed, ai_usage_count=20, ai_usage_limit=20,
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
        else:
            user.ai_usage_count = 20
            user.ai_usage_limit = 20
            db_session.commit()

        # cost=0 should pass even at limit
        check_ai_usage(user, db_session, cost=0)


# ── Regression: paginated format & summary (#1353) ──────────

class TestAdminAIUsageResponseFormat:
    """Regression tests for #1353: admin endpoints must return {items, total}."""

    def test_users_list_returns_paginated(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data, "users list must return {items, total}, not a flat list"
        assert "total" in data
        assert isinstance(data["items"], list)
        assert data["total"] >= 1

    def test_requests_list_returns_paginated(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage/requests", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data, "requests list must return {items, total}, not a flat list"
        assert "total" in data

    def test_summary_endpoint_exists(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage/summary", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_ai_calls" in data
        assert "top_users" in data
        assert isinstance(data["top_users"], list)

    def test_summary_counts_usage(self, client, users, db_session):
        """Summary total_ai_calls reflects user counts."""
        users["student"].ai_usage_count = 7
        db_session.commit()

        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage/summary", headers=headers)
        data = resp.json()
        assert data["total_ai_calls"] >= 7

    def test_summary_top_users_populated(self, client, users, db_session):
        """Top users list should include users with ai_usage_count > 0."""
        users["student"].ai_usage_count = 10
        db_session.commit()

        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage/summary", headers=headers)
        data = resp.json()
        top_ids = [u["id"] for u in data["top_users"]]
        assert users["student"].id in top_ids

    def test_users_list_sort_dir(self, client, users, db_session):
        """sort_dir parameter should be accepted."""
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage?sort_by=ai_usage_count&sort_dir=desc", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_summary_requires_admin(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/admin/ai-usage/summary", headers=headers)
        assert resp.status_code == 403


class TestTrailingSlashRegression:
    """Regression test for #1397: routes must work WITHOUT trailing slash."""

    def test_admin_users_no_trailing_slash(self, client, users):
        headers = _auth(client, users["admin"].email)
        resp = client.get("/api/admin/ai-usage", headers=headers)
        assert resp.status_code == 200, (
            f"GET /api/admin/ai-usage returned {resp.status_code}, expected 200"
        )

    def test_user_usage_no_trailing_slash(self, client, users):
        headers = _auth(client, users["student"].email)
        resp = client.get("/api/ai-usage", headers=headers)
        assert resp.status_code == 200, (
            f"GET /api/ai-usage returned {resp.status_code}, expected 200"
        )
