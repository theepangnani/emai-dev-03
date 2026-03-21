"""Tests for FAQ / Knowledge Base endpoints (GET/POST/PATCH/DELETE /api/faq/*)."""

import pytest
from conftest import PASSWORD, _login, _auth


@pytest.fixture()
def faq_users(db_session):
    """Create FAQ test users: regular user, second user, and admin."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = db_session.query(User).filter(User.email == "faquser@test.com").first()
    if user:
        user2 = db_session.query(User).filter(User.email == "faquser2@test.com").first()
        admin = db_session.query(User).filter(User.email == "faqadmin@test.com").first()
        return {"user": user, "user2": user2, "admin": admin}

    hashed = get_password_hash(PASSWORD)
    user = User(email="faquser@test.com", full_name="FAQ User", role=UserRole.STUDENT, hashed_password=hashed)
    user2 = User(email="faquser2@test.com", full_name="FAQ User2", role=UserRole.PARENT, hashed_password=hashed)
    admin = User(email="faqadmin@test.com", full_name="FAQ Admin", role=UserRole.ADMIN, hashed_password=hashed)
    db_session.add_all([user, user2, admin])
    db_session.commit()
    return {"user": user, "user2": user2, "admin": admin}


# ── Question CRUD ──────────────────────────────────────────────


class TestFAQQuestions:
    def test_list_questions_empty(self, client, faq_users):
        headers = _auth(client, "faquser@test.com")
        resp = client.get("/api/faq/questions", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_question(self, client, faq_users):
        headers = _auth(client, "faquser@test.com")
        resp = client.post("/api/faq/questions", json={
            "title": "How do I reset my password?",
            "description": "I forgot my password and need help.",
            "category": "account",
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "How do I reset my password?"
        assert data["category"] == "account"
        assert data["status"] == "open"
        assert data["creator_name"] == "FAQ User"

    def test_create_question_missing_title(self, client, faq_users):
        headers = _auth(client, "faquser@test.com")
        resp = client.post("/api/faq/questions", json={
            "description": "No title",
        }, headers=headers)
        assert resp.status_code == 422

    def test_create_question_requires_auth(self, client):
        resp = client.post("/api/faq/questions", json={"title": "Test"})
        assert resp.status_code == 401

    def test_list_questions_with_data(self, client, faq_users):
        headers = _auth(client, "faquser@test.com")
        resp = client.get("/api/faq/questions", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert any(q["title"] == "How do I reset my password?" for q in data)

    def test_list_questions_filter_by_category(self, client, faq_users):
        headers = _auth(client, "faquser@test.com")
        resp = client.get("/api/faq/questions", params={"category": "account"}, headers=headers)
        assert resp.status_code == 200
        for q in resp.json():
            assert q["category"] == "account"

    def test_list_questions_search(self, client, faq_users):
        headers = _auth(client, "faquser@test.com")
        resp = client.get("/api/faq/questions", params={"search": "password"}, headers=headers)
        assert resp.status_code == 200
        assert any("password" in q["title"].lower() for q in resp.json())

    def test_get_question_detail(self, client, faq_users):
        headers = _auth(client, "faquser@test.com")
        # Get a question ID first
        questions = client.get("/api/faq/questions", headers=headers).json()
        q_id = questions[0]["id"]

        resp = client.get(f"/api/faq/questions/{q_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == q_id
        assert "answers" in data
        assert data["view_count"] >= 1  # view_count incremented

    def test_update_own_question(self, client, faq_users):
        headers = _auth(client, "faquser@test.com")
        questions = client.get("/api/faq/questions", headers=headers).json()
        q_id = questions[0]["id"]

        resp = client.patch(f"/api/faq/questions/{q_id}", json={
            "title": "How do I reset my password? (updated)",
        }, headers=headers)
        assert resp.status_code == 200
        assert "updated" in resp.json()["title"]

    def test_update_other_users_question_forbidden(self, client, faq_users):
        # user created the question, user2 tries to edit
        user_headers = _auth(client, "faquser@test.com")
        questions = client.get("/api/faq/questions", headers=user_headers).json()
        q_id = questions[0]["id"]

        user2_headers = _auth(client, "faquser2@test.com")
        resp = client.patch(f"/api/faq/questions/{q_id}", json={
            "title": "Hijacked!",
        }, headers=user2_headers)
        assert resp.status_code == 403

    def test_admin_can_edit_any_question(self, client, faq_users):
        user_headers = _auth(client, "faquser@test.com")
        questions = client.get("/api/faq/questions", headers=user_headers).json()
        q_id = questions[0]["id"]

        admin_headers = _auth(client, "faqadmin@test.com")
        resp = client.patch(f"/api/faq/questions/{q_id}", json={
            "category": "getting-started",
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["category"] == "getting-started"

    def test_delete_question_soft(self, client, faq_users):
        # Create a question to delete
        headers = _auth(client, "faquser@test.com")
        create = client.post("/api/faq/questions", json={
            "title": "To be deleted",
            "category": "other",
        }, headers=headers)
        q_id = create.json()["id"]

        resp = client.delete(f"/api/faq/questions/{q_id}", headers=headers)
        assert resp.status_code == 204

        # Should not appear in list
        questions = client.get("/api/faq/questions", headers=headers).json()
        assert not any(q["id"] == q_id for q in questions)

    def test_delete_other_users_question_forbidden(self, client, faq_users):
        user_headers = _auth(client, "faquser@test.com")
        create = client.post("/api/faq/questions", json={
            "title": "User's question",
            "category": "other",
        }, headers=user_headers)
        q_id = create.json()["id"]

        user2_headers = _auth(client, "faquser2@test.com")
        resp = client.delete(f"/api/faq/questions/{q_id}", headers=user2_headers)
        assert resp.status_code == 403

    def test_create_question_invalid_category(self, client, faq_users):
        """Creating a question with an invalid category returns 422."""
        headers = _auth(client, "faquser@test.com")
        resp = client.post("/api/faq/questions", json={
            "title": "Bad category test",
            "category": "nonexistent-category",
        }, headers=headers)
        assert resp.status_code == 422

    def test_admin_can_delete_any_question(self, client, faq_users):
        """Admin can soft-delete a question created by another user."""
        user_headers = _auth(client, "faquser@test.com")
        create = client.post("/api/faq/questions", json={
            "title": "Admin will delete this question",
            "category": "other",
        }, headers=user_headers)
        q_id = create.json()["id"]

        admin_headers = _auth(client, "faqadmin@test.com")
        resp = client.delete(f"/api/faq/questions/{q_id}", headers=admin_headers)
        assert resp.status_code == 204

        # Verify it is gone from the list
        questions = client.get("/api/faq/questions", headers=user_headers).json()
        assert not any(q["id"] == q_id for q in questions)

    def test_pinned_questions_appear_first(self, client, faq_users):
        """Pinned questions should appear before non-pinned in the list."""
        user_headers = _auth(client, "faquser@test.com")
        admin_headers = _auth(client, "faqadmin@test.com")

        # Create two questions
        r1 = client.post("/api/faq/questions", json={
            "title": "PinOrderTestNotPinned",
            "category": "other",
        }, headers=user_headers)
        q1_id = r1.json()["id"]

        r2 = client.post("/api/faq/questions", json={
            "title": "PinOrderTestPinned",
            "category": "other",
        }, headers=user_headers)
        q2_id = r2.json()["id"]

        # Pin the second one
        client.patch(f"/api/faq/admin/questions/{q2_id}/pin", json={
            "is_pinned": True,
        }, headers=admin_headers)

        # List all and find our test questions
        questions = client.get("/api/faq/questions", params={
            "search": "PinOrderTest",
        }, headers=user_headers).json()
        assert len(questions) >= 2

        # The pinned one must appear before the non-pinned one
        ids = [q["id"] for q in questions]
        assert ids.index(q2_id) < ids.index(q1_id)

    def test_list_questions_requires_auth(self, client):
        """Listing questions without auth returns 401."""
        resp = client.get("/api/faq/questions")
        assert resp.status_code == 401

    def test_get_question_requires_auth(self, client):
        """Getting question detail without auth returns 401."""
        resp = client.get("/api/faq/questions/1")
        assert resp.status_code == 401

    def test_create_question_default_category(self, client, faq_users):
        """Creating a question without category defaults to 'other'."""
        headers = _auth(client, "faquser@test.com")
        resp = client.post("/api/faq/questions", json={
            "title": "No category specified question",
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["category"] == "other"



# ── Answer CRUD ────────────────────────────────────────────────


class TestFAQAnswers:
    @pytest.fixture(autouse=True)
    def _setup_question(self, client, faq_users):
        """Create a question for answer tests."""
        headers = _auth(client, "faquser@test.com")
        resp = client.post("/api/faq/questions", json={
            "title": "Answer test question",
            "category": "study-tools",
        }, headers=headers)
        self.question_id = resp.json()["id"]

    def test_submit_answer(self, client, faq_users):
        headers = _auth(client, "faquser2@test.com")
        resp = client.post(f"/api/faq/questions/{self.question_id}/answers", json={
            "content": "You can reset your password from the login page. Click Forgot Password.",
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["creator_name"] == "FAQ User2"

    def test_admin_answer_auto_approved(self, client, faq_users):
        admin_headers = _auth(client, "faqadmin@test.com")
        resp = client.post(f"/api/faq/questions/{self.question_id}/answers", json={
            "content": "Admin auto-approved answer for this test question.",
        }, headers=admin_headers)
        assert resp.status_code == 201
        assert resp.json()["status"] == "approved"

    def test_submit_answer_too_short(self, client, faq_users):
        headers = _auth(client, "faquser@test.com")
        resp = client.post(f"/api/faq/questions/{self.question_id}/answers", json={
            "content": "Short",
        }, headers=headers)
        assert resp.status_code == 422

    def test_edit_own_pending_answer(self, client, faq_users):
        # Submit an answer
        headers = _auth(client, "faquser2@test.com")
        create = client.post(f"/api/faq/questions/{self.question_id}/answers", json={
            "content": "Original answer content for editing test case here.",
        }, headers=headers)
        answer_id = create.json()["id"]

        # Edit it
        resp = client.patch(f"/api/faq/answers/{answer_id}", json={
            "content": "Updated answer content for editing test case here.",
        }, headers=headers)
        assert resp.status_code == 200
        assert "Updated" in resp.json()["content"]

    def test_edit_other_users_answer_forbidden(self, client, faq_users):
        # user2 creates answer
        user2_headers = _auth(client, "faquser2@test.com")
        create = client.post(f"/api/faq/questions/{self.question_id}/answers", json={
            "content": "User2's answer for forbidden edit test case here.",
        }, headers=user2_headers)
        answer_id = create.json()["id"]

        # user tries to edit
        user_headers = _auth(client, "faquser@test.com")
        resp = client.patch(f"/api/faq/answers/{answer_id}", json={
            "content": "Trying to hijack user2's answer which should be forbidden!",
        }, headers=user_headers)
        assert resp.status_code == 403

    def test_edit_approved_answer_fails(self, client, faq_users):
        """Cannot edit an answer that has already been approved."""
        # user2 submits answer
        user2_headers = _auth(client, "faquser2@test.com")
        create = client.post(f"/api/faq/questions/{self.question_id}/answers", json={
            "content": "Answer that will be approved and then edit attempted.",
        }, headers=user2_headers)
        answer_id = create.json()["id"]

        # admin approves it
        admin_headers = _auth(client, "faqadmin@test.com")
        client.patch(f"/api/faq/admin/answers/{answer_id}/approve", headers=admin_headers)

        # user2 tries to edit approved answer
        resp = client.patch(f"/api/faq/answers/{answer_id}", json={
            "content": "Trying to edit an already approved answer should fail!",
        }, headers=user2_headers)
        assert resp.status_code == 400



# ── Admin Approval Workflow ────────────────────────────────────


class TestFAQAdmin:
    @pytest.fixture(autouse=True)
    def _setup(self, client, faq_users):
        """Create a question with a pending answer for admin tests."""
        user_headers = _auth(client, "faquser@test.com")
        q_resp = client.post("/api/faq/questions", json={
            "title": "Admin test question",
            "category": "courses",
        }, headers=user_headers)
        self.question_id = q_resp.json()["id"]

        user2_headers = _auth(client, "faquser2@test.com")
        a_resp = client.post(f"/api/faq/questions/{self.question_id}/answers", json={
            "content": "Pending answer waiting for admin approval in this test.",
        }, headers=user2_headers)
        self.answer_id = a_resp.json()["id"]

    def test_list_pending_admin_only(self, client, faq_users):
        admin_headers = _auth(client, "faqadmin@test.com")
        resp = client.get("/api/faq/admin/pending", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_approve_answer(self, client, faq_users):
        admin_headers = _auth(client, "faqadmin@test.com")
        resp = client.patch(f"/api/faq/admin/answers/{self.answer_id}/approve", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"
        assert resp.json()["reviewer_name"] == "FAQ Admin"

    def test_reject_answer(self, client, faq_users):
        # Create a new pending answer to reject
        user2_headers = _auth(client, "faquser2@test.com")
        a_resp = client.post(f"/api/faq/questions/{self.question_id}/answers", json={
            "content": "This answer will be rejected by the admin reviewer.",
        }, headers=user2_headers)
        new_id = a_resp.json()["id"]

        admin_headers = _auth(client, "faqadmin@test.com")
        resp = client.patch(f"/api/faq/admin/answers/{new_id}/reject", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    def test_pin_question(self, client, faq_users):
        admin_headers = _auth(client, "faqadmin@test.com")
        resp = client.patch(f"/api/faq/admin/questions/{self.question_id}/pin", json={
            "is_pinned": True,
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["is_pinned"] is True

    def test_unpin_question(self, client, faq_users):
        admin_headers = _auth(client, "faqadmin@test.com")
        # Pin first
        client.patch(f"/api/faq/admin/questions/{self.question_id}/pin", json={
            "is_pinned": True,
        }, headers=admin_headers)
        # Then unpin
        resp = client.patch(f"/api/faq/admin/questions/{self.question_id}/pin", json={
            "is_pinned": False,
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["is_pinned"] is False

    def test_mark_official(self, client, faq_users):
        admin_headers = _auth(client, "faqadmin@test.com")
        # Approve first
        client.patch(f"/api/faq/admin/answers/{self.answer_id}/approve", headers=admin_headers)
        # Mark official
        resp = client.patch(f"/api/faq/admin/answers/{self.answer_id}/mark-official", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["is_official"] is True

    def test_mark_official_pending_answer_fails(self, client, faq_users):
        """Cannot mark a pending answer as official."""
        # Create a new pending answer
        user2_headers = _auth(client, "faquser2@test.com")
        a_resp = client.post(f"/api/faq/questions/{self.question_id}/answers", json={
            "content": "Pending answer cannot be marked official without approval.",
        }, headers=user2_headers)
        pending_id = a_resp.json()["id"]

        admin_headers = _auth(client, "faqadmin@test.com")
        resp = client.patch(f"/api/faq/admin/answers/{pending_id}/mark-official", headers=admin_headers)
        assert resp.status_code == 400

    def test_delete_answer_admin(self, client, faq_users):
        # Create an answer to delete
        user2_headers = _auth(client, "faquser2@test.com")
        a_resp = client.post(f"/api/faq/questions/{self.question_id}/answers", json={
            "content": "This answer will be deleted by the admin user.",
        }, headers=user2_headers)
        del_id = a_resp.json()["id"]

        admin_headers = _auth(client, "faqadmin@test.com")
        resp = client.delete(f"/api/faq/admin/answers/{del_id}", headers=admin_headers)
        assert resp.status_code == 204

    def test_create_official_faq(self, client, faq_users):
        admin_headers = _auth(client, "faqadmin@test.com")
        resp = client.post("/api/faq/admin/questions", json={
            "title": "Official: How do I connect Google Classroom?",
            "description": "Step-by-step guide to connecting Google Classroom.",
            "category": "google-classroom",
            "answer_content": "Go to your dashboard, click 'Connect Google Classroom', and follow the OAuth prompts.",
            "is_official": True,
        }, headers=admin_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "answered"
        assert len(data["answers"]) == 1
        assert data["answers"][0]["status"] == "approved"
        assert data["answers"][0]["is_official"] is True

    def test_create_official_faq_non_admin_forbidden(self, client, faq_users):
        user_headers = _auth(client, "faquser@test.com")
        resp = client.post("/api/faq/admin/questions", json={
            "title": "Not allowed",
            "answer_content": "Non-admin cannot create official FAQ entries.",
        }, headers=user_headers)
        assert resp.status_code == 403

    def test_approve_already_approved_answer_fails(self, client, faq_users):
        """Approving an already-approved answer returns 400."""
        admin_headers = _auth(client, "faqadmin@test.com")
        # Approve first
        client.patch(f"/api/faq/admin/answers/{self.answer_id}/approve", headers=admin_headers)
        # Approve again
        resp = client.patch(f"/api/faq/admin/answers/{self.answer_id}/approve", headers=admin_headers)
        assert resp.status_code == 400

    def test_reject_already_rejected_answer_fails(self, client, faq_users):
        """Rejecting an already-rejected answer returns 400."""
        # Create a new pending answer
        user2_headers = _auth(client, "faquser2@test.com")
        a_resp = client.post(f"/api/faq/questions/{self.question_id}/answers", json={
            "content": "This answer will be double-rejected to test idempotency.",
        }, headers=user2_headers)
        new_id = a_resp.json()["id"]

        admin_headers = _auth(client, "faqadmin@test.com")
        client.patch(f"/api/faq/admin/answers/{new_id}/reject", headers=admin_headers)
        resp = client.patch(f"/api/faq/admin/answers/{new_id}/reject", headers=admin_headers)
        assert resp.status_code == 400

    def test_toggle_official_off(self, client, faq_users):
        """Marking official answer again should toggle it off."""
        admin_headers = _auth(client, "faqadmin@test.com")
        # Approve
        client.patch(f"/api/faq/admin/answers/{self.answer_id}/approve", headers=admin_headers)
        # Mark official
        client.patch(f"/api/faq/admin/answers/{self.answer_id}/mark-official", headers=admin_headers)
        # Toggle off
        resp = client.patch(f"/api/faq/admin/answers/{self.answer_id}/mark-official", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["is_official"] is False

    def test_question_status_updates_on_first_approved_answer(self, client, faq_users):
        """Question status should change from 'open' to 'answered' when first answer is approved."""
        user_headers = _auth(client, "faquser@test.com")
        admin_headers = _auth(client, "faqadmin@test.com")

        # Verify question is open
        q_resp = client.get(f"/api/faq/questions/{self.question_id}", headers=user_headers)
        assert q_resp.json()["status"] == "open"

        # Approve the pending answer
        client.patch(f"/api/faq/admin/answers/{self.answer_id}/approve", headers=admin_headers)

        # Verify question is now answered
        q_resp = client.get(f"/api/faq/questions/{self.question_id}", headers=user_headers)
        assert q_resp.json()["status"] == "answered"



# ── Parameterized 404 tests ───────────────────────────────────


@pytest.mark.parametrize("method,url,json_body", [
    ("GET", "/api/faq/questions/99999", None),
    ("DELETE", "/api/faq/questions/99999", None),
    ("PATCH", "/api/faq/questions/99999", {"title": "x"}),
    ("POST", "/api/faq/questions/99999/answers", {"content": "x" * 20}),
    ("PATCH", "/api/faq/answers/99999", {"content": "x" * 20}),
    ("DELETE", "/api/faq/admin/answers/99999", None),
    ("PATCH", "/api/faq/admin/answers/99999/approve", None),
    ("PATCH", "/api/faq/admin/answers/99999/reject", None),
    ("PATCH", "/api/faq/admin/answers/99999/mark-official", None),
    ("PATCH", "/api/faq/admin/questions/99999/pin", {"is_pinned": True}),
])
def test_nonexistent_resource_returns_404(client, faq_users, method, url, json_body):
    headers = _auth(client, faq_users["admin"].email)
    kwargs = {"headers": headers}
    if json_body:
        kwargs["json"] = json_body
    resp = getattr(client, method.lower())(url, **kwargs)
    assert resp.status_code == 404


# ── Parameterized non-admin forbidden tests ───────────────────


@pytest.mark.parametrize("method,url_template,json_body", [
    ("GET", "/api/faq/admin/pending", None),
    ("PATCH", "/api/faq/admin/answers/{answer_id}/approve", None),
    ("PATCH", "/api/faq/admin/answers/{answer_id}/reject", None),
    ("PATCH", "/api/faq/admin/answers/{answer_id}/mark-official", None),
    ("PATCH", "/api/faq/admin/questions/{question_id}/pin", {"is_pinned": True}),
    ("DELETE", "/api/faq/admin/answers/{answer_id}", None),
])
def test_non_admin_forbidden(client, faq_users, method, url_template, json_body):
    """Non-admin users cannot access admin FAQ endpoints."""
    # Create a question + answer for URL substitution
    user_headers = _auth(client, faq_users["user"].email)
    q_resp = client.post("/api/faq/questions", json={
        "title": "Forbidden test question", "category": "other",
    }, headers=user_headers)
    q_id = q_resp.json()["id"]

    user2_headers = _auth(client, faq_users["user2"].email)
    a_resp = client.post(f"/api/faq/questions/{q_id}/answers", json={
        "content": "Forbidden test answer content for parameterized test.",
    }, headers=user2_headers)
    a_id = a_resp.json()["id"]

    url = url_template.format(answer_id=a_id, question_id=q_id)
    kwargs = {"headers": user_headers}
    if json_body:
        kwargs["json"] = json_body
    resp = getattr(client, method.lower())(url, **kwargs)
    assert resp.status_code == 403


# ── Visibility ─────────────────────────────────────────────────


class TestFAQVisibility:
    def test_non_admin_cannot_see_pending_answers(self, client, faq_users):
        """Non-admin user should only see approved answers on question detail."""
        # Create question + pending answer
        user_headers = _auth(client, "faquser@test.com")
        q_resp = client.post("/api/faq/questions", json={
            "title": "Visibility test question",
            "category": "other",
        }, headers=user_headers)
        q_id = q_resp.json()["id"]

        user2_headers = _auth(client, "faquser2@test.com")
        client.post(f"/api/faq/questions/{q_id}/answers", json={
            "content": "This pending answer should not be visible to non-admin users.",
        }, headers=user2_headers)

        # Non-admin gets detail — should not see pending
        resp = client.get(f"/api/faq/questions/{q_id}", headers=user_headers)
        assert resp.status_code == 200
        for answer in resp.json()["answers"]:
            assert answer["status"] == "approved"

    def test_admin_sees_all_answer_statuses(self, client, faq_users):
        """Admin should see pending, approved, and rejected answers."""
        user_headers = _auth(client, "faquser@test.com")
        q_resp = client.post("/api/faq/questions", json={
            "title": "Admin visibility test",
            "category": "other",
        }, headers=user_headers)
        q_id = q_resp.json()["id"]

        # Submit a pending answer
        user2_headers = _auth(client, "faquser2@test.com")
        client.post(f"/api/faq/questions/{q_id}/answers", json={
            "content": "Pending answer visible only to admin in this test.",
        }, headers=user2_headers)

        # Admin views detail
        admin_headers = _auth(client, "faqadmin@test.com")
        resp = client.get(f"/api/faq/questions/{q_id}", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()["answers"]) >= 1


# ── Error Code Lookup ──────────────────────────────────────────


class TestFAQErrorCodeLookup:
    def test_lookup_existing_error_code(self, client, faq_users, db_session):
        """Create a question with error_code and look it up."""
        from app.models.faq import FAQQuestion

        q = FAQQuestion(
            title="Google Sync Troubleshooting",
            category="google-classroom",
            error_code="TEST_ERROR_CODE",
            created_by_user_id=faq_users["admin"].id,
        )
        db_session.add(q)
        db_session.commit()

        headers = _auth(client, "faquser@test.com")
        resp = client.get("/api/faq/by-error-code/TEST_ERROR_CODE", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Google Sync Troubleshooting"
        assert data["id"] == q.id

    def test_lookup_nonexistent_error_code(self, client, faq_users):
        headers = _auth(client, "faquser@test.com")
        resp = client.get("/api/faq/by-error-code/NONEXISTENT_CODE", headers=headers)
        assert resp.status_code == 404


# ── Search Integration (DEPRECATED — /api/search removed #1698) ────


@pytest.mark.skip(reason="GlobalSearch endpoint deprecated (#1698)")
class TestFAQSearch:
    def test_global_search_includes_faq(self, client, faq_users):
        """FAQ questions should appear in global search results."""
        # Create a question with searchable title
        headers = _auth(client, "faquser@test.com")
        client.post("/api/faq/questions", json={
            "title": "UniqueSearchableFAQTerm question",
            "category": "other",
        }, headers=headers)

        resp = client.get("/api/search", params={"q": "UniqueSearchableFAQTerm"}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        faq_groups = [g for g in data["groups"] if g["entity_type"] == "faq"]
        assert len(faq_groups) == 1
        assert faq_groups[0]["total"] >= 1

    def test_archived_faq_excluded_from_search(self, client, faq_users, db_session):
        """Archived FAQ questions should not appear in search."""
        from datetime import datetime, timezone
        from app.models.faq import FAQQuestion

        q = FAQQuestion(
            title="ArchivedFAQSearchTest entry",
            category="other",
            created_by_user_id=faq_users["user"].id,
            archived_at=datetime.now(timezone.utc),
        )
        db_session.add(q)
        db_session.commit()

        headers = _auth(client, "faquser@test.com")
        resp = client.get("/api/search", params={"q": "ArchivedFAQSearchTest"}, headers=headers)
        data = resp.json()
        faq_groups = [g for g in data["groups"] if g["entity_type"] == "faq"]
        for g in faq_groups:
            for item in g["items"]:
                assert item["id"] != q.id

    def test_search_filtered_by_faq_type(self, client, faq_users):
        """Searching with types=faq should only return FAQ results."""
        headers = _auth(client, "faquser@test.com")
        client.post("/api/faq/questions", json={
            "title": "FilteredTypeSearchFAQ question",
            "category": "other",
        }, headers=headers)

        resp = client.get("/api/search", params={
            "q": "FilteredTypeSearchFAQ",
            "types": "faq",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # Should only have FAQ group
        entity_types = {g["entity_type"] for g in data["groups"]}
        assert entity_types == {"faq"}
        faq_groups = [g for g in data["groups"] if g["entity_type"] == "faq"]
        assert faq_groups[0]["total"] >= 1

    def test_search_faq_items_have_correct_url(self, client, faq_users):
        """FAQ search results should have /faq/{id} URLs."""
        headers = _auth(client, "faquser@test.com")
        resp = client.post("/api/faq/questions", json={
            "title": "FAQUrlVerification unique question",
            "category": "other",
        }, headers=headers)
        q_id = resp.json()["id"]

        search_resp = client.get("/api/search", params={
            "q": "FAQUrlVerification",
            "types": "faq",
        }, headers=headers)
        data = search_resp.json()
        faq_groups = [g for g in data["groups"] if g["entity_type"] == "faq"]
        assert len(faq_groups) == 1
        matching = [i for i in faq_groups[0]["items"] if i["id"] == q_id]
        assert len(matching) == 1
        assert matching[0]["url"] == f"/faq/{q_id}"


# ── Seed Service ──────────────────────────────────────────────


class TestFAQSeed:
    def test_seed_creates_entries(self, db_session):
        """Seed service creates FAQ entries from seed.json when table is empty."""
        from app.models.faq import FAQQuestion, FAQAnswer
        from app.services.faq_seed_service import seed_faq, SEED_FILE

        # Clear existing FAQ questions for this test
        db_session.query(FAQAnswer).delete()
        db_session.query(FAQQuestion).delete()
        db_session.commit()

        count = seed_faq(db_session)

        # Verify entries were created
        assert count > 0
        questions = db_session.query(FAQQuestion).all()
        assert len(questions) == count

        # Verify each question has an answer
        for q in questions:
            answers = db_session.query(FAQAnswer).filter(FAQAnswer.question_id == q.id).all()
            assert len(answers) == 1
            assert answers[0].status == "approved"
            assert answers[0].is_official is True

    def test_seed_is_idempotent(self, db_session):
        """Running seed a second time should not create duplicate entries."""
        from app.models.faq import FAQQuestion
        from app.services.faq_seed_service import seed_faq

        # Seed may already have entries from previous test
        first_count = db_session.query(FAQQuestion).count()
        if first_count == 0:
            seed_faq(db_session)
            first_count = db_session.query(FAQQuestion).count()

        # Run again - should be idempotent
        second_result = seed_faq(db_session)
        assert second_result == 0  # No new entries created

        second_count = db_session.query(FAQQuestion).count()
        assert second_count == first_count

    def test_seed_entries_have_correct_categories(self, db_session):
        """Seeded entries should have valid FAQ categories."""
        from app.models.faq import FAQQuestion, FAQCategory
        from app.services.faq_seed_service import seed_faq

        # Ensure seeded
        if db_session.query(FAQQuestion).count() == 0:
            seed_faq(db_session)

        valid_categories = {c.value for c in FAQCategory}
        questions = db_session.query(FAQQuestion).all()
        for q in questions:
            assert q.category in valid_categories, f"Invalid category: {q.category}"

    def test_seed_entries_have_answered_status(self, db_session):
        """All seeded questions should have 'answered' status."""
        from app.models.faq import FAQQuestion, FAQQuestionStatus
        from app.services.faq_seed_service import seed_faq

        if db_session.query(FAQQuestion).count() == 0:
            seed_faq(db_session)

        questions = db_session.query(FAQQuestion).all()
        for q in questions:
            assert q.status == FAQQuestionStatus.ANSWERED.value

    def test_seed_has_minimum_entries(self, db_session):
        """Seed file should contain at least 10 entries per requirements."""
        from app.services.faq_seed_service import SEED_FILE
        import json

        assert SEED_FILE.exists(), f"Seed file missing: {SEED_FILE}"
        with open(SEED_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
        assert len(entries) >= 10, f"Expected >= 10 seed entries, got {len(entries)}"

    def test_seed_file_has_pinned_entries(self, db_session):
        """Seed file should include some pinned entries."""
        from app.services.faq_seed_service import SEED_FILE
        import json

        with open(SEED_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
        pinned = [e for e in entries if e.get("is_pinned")]
        assert len(pinned) >= 1, "Seed should have at least one pinned entry"

    def test_seed_file_has_error_codes(self, db_session):
        """Seed file should include entries with error_code mappings."""
        from app.services.faq_seed_service import SEED_FILE
        import json

        with open(SEED_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
        with_codes = [e for e in entries if e.get("error_code")]
        assert len(with_codes) >= 1, "Seed should have at least one entry with error_code"
