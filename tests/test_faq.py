"""Tests for FAQ / Knowledge Base endpoints (GET/POST/PATCH/DELETE /api/faq/*)."""

import pytest

PASSWORD = "Password123!"


def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}


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

    def test_get_question_not_found(self, client, faq_users):
        headers = _auth(client, "faquser@test.com")
        resp = client.get("/api/faq/questions/99999", headers=headers)
        assert resp.status_code == 404

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

    def test_submit_answer_question_not_found(self, client, faq_users):
        headers = _auth(client, "faquser@test.com")
        resp = client.post("/api/faq/questions/99999/answers", json={
            "content": "This answer goes nowhere because the question doesn't exist.",
        }, headers=headers)
        assert resp.status_code == 404

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

    def test_edit_nonexistent_answer_404(self, client, faq_users):
        """Editing a non-existent answer returns 404."""
        headers = _auth(client, "faquser@test.com")
        resp = client.patch("/api/faq/answers/99999", json={
            "content": "This answer does not exist so should return 404.",
        }, headers=headers)
        assert resp.status_code == 404


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

    def test_list_pending_non_admin_forbidden(self, client, faq_users):
        user_headers = _auth(client, "faquser@test.com")
        resp = client.get("/api/faq/admin/pending", headers=user_headers)
        assert resp.status_code == 403

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

    def test_approve_non_admin_forbidden(self, client, faq_users):
        user_headers = _auth(client, "faquser@test.com")
        resp = client.patch(f"/api/faq/admin/answers/{self.answer_id}/approve", headers=user_headers)
        assert resp.status_code == 403

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

    def test_pin_non_admin_forbidden(self, client, faq_users):
        user_headers = _auth(client, "faquser@test.com")
        resp = client.patch(f"/api/faq/admin/questions/{self.question_id}/pin", json={
            "is_pinned": True,
        }, headers=user_headers)
        assert resp.status_code == 403

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


# ── Search Integration ─────────────────────────────────────────


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
