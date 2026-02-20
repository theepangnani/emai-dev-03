import json

import pytest

PASSWORD = "Password123!"


def _login(client, email):
    resp = client.post("/api/auth/login", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(client, email):
    return {"Authorization": f"Bearer {_login(client, email)}"}


@pytest.fixture()
def setup(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student
    from app.models.study_guide import StudyGuide

    student = db_session.query(User).filter(User.email == "qr_student@test.com").first()
    if student:
        outsider = db_session.query(User).filter(User.email == "qr_outsider@test.com").first()
        quiz_guide = db_session.query(StudyGuide).filter(
            StudyGuide.user_id == student.id, StudyGuide.guide_type == "quiz"
        ).first()
        non_quiz_guide = db_session.query(StudyGuide).filter(
            StudyGuide.user_id == student.id, StudyGuide.guide_type == "study_guide"
        ).first()
        return {
            "student": student, "outsider": outsider,
            "quiz_guide": quiz_guide, "non_quiz_guide": non_quiz_guide,
        }

    hashed = get_password_hash(PASSWORD)
    student = User(email="qr_student@test.com", full_name="QR Student", role=UserRole.STUDENT, hashed_password=hashed)
    outsider = User(email="qr_outsider@test.com", full_name="QR Outsider", role=UserRole.STUDENT, hashed_password=hashed)
    db_session.add_all([student, outsider])
    db_session.flush()

    student_rec = Student(user_id=student.id)
    db_session.add(student_rec)
    db_session.flush()

    # Create a quiz guide and a non-quiz guide
    quiz_guide = StudyGuide(
        user_id=student.id,
        title="Test Quiz",
        content=json.dumps([
            {"question": "Q1?", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "correct_answer": "A", "explanation": "A is correct"},
            {"question": "Q2?", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "correct_answer": "B", "explanation": "B is correct"},
        ]),
        guide_type="quiz",
    )
    non_quiz_guide = StudyGuide(
        user_id=student.id,
        title="Test Study Guide",
        content="Some study content",
        guide_type="study_guide",
    )
    db_session.add_all([quiz_guide, non_quiz_guide])
    db_session.commit()

    return {
        "student": student, "outsider": outsider,
        "quiz_guide": quiz_guide, "non_quiz_guide": non_quiz_guide,
    }


# ── Save Tests ───────────────────────────────────────────────────

class TestSaveQuizResult:
    def test_save_success(self, client, setup):
        headers = _auth(client, "qr_student@test.com")
        resp = client.post("/api/quiz-results/", json={
            "study_guide_id": setup["quiz_guide"].id,
            "score": 1,
            "total_questions": 2,
            "answers": {0: "A", 1: "C"},
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["score"] == 1
        assert data["total_questions"] == 2
        assert data["percentage"] == 50.0
        assert data["attempt_number"] == 1
        assert data["quiz_title"] == "Test Quiz"

    def test_auto_increment_attempt(self, client, setup):
        headers = _auth(client, "qr_student@test.com")
        # First attempt
        resp1 = client.post("/api/quiz-results/", json={
            "study_guide_id": setup["quiz_guide"].id,
            "score": 1,
            "total_questions": 2,
            "answers": {0: "A", 1: "C"},
        }, headers=headers)
        # Second attempt
        resp2 = client.post("/api/quiz-results/", json={
            "study_guide_id": setup["quiz_guide"].id,
            "score": 2,
            "total_questions": 2,
            "answers": {0: "A", 1: "B"},
        }, headers=headers)
        assert resp2.status_code == 201
        assert resp2.json()["attempt_number"] > resp1.json()["attempt_number"]

    def test_save_404_bad_guide(self, client, setup):
        headers = _auth(client, "qr_student@test.com")
        resp = client.post("/api/quiz-results/", json={
            "study_guide_id": 99999,
            "score": 1,
            "total_questions": 2,
            "answers": {0: "A", 1: "C"},
        }, headers=headers)
        assert resp.status_code == 404

    def test_save_400_non_quiz_guide(self, client, setup):
        headers = _auth(client, "qr_student@test.com")
        resp = client.post("/api/quiz-results/", json={
            "study_guide_id": setup["non_quiz_guide"].id,
            "score": 1,
            "total_questions": 2,
            "answers": {0: "A"},
        }, headers=headers)
        assert resp.status_code == 400

    def test_save_unauthenticated(self, client, setup):
        resp = client.post("/api/quiz-results/", json={
            "study_guide_id": setup["quiz_guide"].id,
            "score": 1,
            "total_questions": 2,
            "answers": {0: "A"},
        })
        assert resp.status_code == 401


# ── List Tests ───────────────────────────────────────────────────

class TestListQuizResults:
    def test_list_own_results(self, client, setup):
        headers = _auth(client, "qr_student@test.com")
        # Create a result first
        client.post("/api/quiz-results/", json={
            "study_guide_id": setup["quiz_guide"].id,
            "score": 2,
            "total_questions": 2,
            "answers": {0: "A", 1: "B"},
        }, headers=headers)
        resp = client.get("/api/quiz-results/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert all(r["quiz_title"] is not None for r in data)

    def test_filter_by_study_guide_id(self, client, setup):
        headers = _auth(client, "qr_student@test.com")
        resp = client.get(f"/api/quiz-results/?study_guide_id={setup['quiz_guide'].id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert all(r["study_guide_id"] == setup["quiz_guide"].id for r in data)

    def test_empty_history_for_outsider(self, client, setup):
        headers = _auth(client, "qr_outsider@test.com")
        resp = client.get("/api/quiz-results/", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_results_desc_order(self, client, setup):
        headers = _auth(client, "qr_student@test.com")
        resp = client.get("/api/quiz-results/", headers=headers)
        data = resp.json()
        if len(data) >= 2:
            assert data[0]["completed_at"] >= data[1]["completed_at"]


# ── Stats Tests ──────────────────────────────────────────────────

class TestQuizStats:
    def test_stats_correct_aggregates(self, client, setup):
        headers = _auth(client, "qr_student@test.com")
        resp = client.get("/api/quiz-results/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_attempts"] >= 0
        assert data["unique_quizzes"] >= 0
        assert 0 <= data["average_score"] <= 100
        assert 0 <= data["best_score"] <= 100
        assert data["recent_trend"] in ("improving", "declining", "stable")

    def test_stats_empty_returns_zeros(self, client, setup):
        headers = _auth(client, "qr_outsider@test.com")
        resp = client.get("/api/quiz-results/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_attempts"] == 0
        assert data["unique_quizzes"] == 0
        assert data["average_score"] == 0.0
        assert data["best_score"] == 0.0
        assert data["recent_trend"] == "stable"


# ── Get Single Tests ─────────────────────────────────────────────

class TestGetQuizResult:
    def test_owner_access(self, client, setup):
        headers = _auth(client, "qr_student@test.com")
        # Create one
        save_resp = client.post("/api/quiz-results/", json={
            "study_guide_id": setup["quiz_guide"].id,
            "score": 2,
            "total_questions": 2,
            "answers": {0: "A", 1: "B"},
        }, headers=headers)
        result_id = save_resp.json()["id"]
        resp = client.get(f"/api/quiz-results/{result_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == result_id

    def test_outsider_404(self, client, setup):
        headers_student = _auth(client, "qr_student@test.com")
        save_resp = client.post("/api/quiz-results/", json={
            "study_guide_id": setup["quiz_guide"].id,
            "score": 1,
            "total_questions": 2,
            "answers": {0: "A", 1: "C"},
        }, headers=headers_student)
        result_id = save_resp.json()["id"]
        headers_outsider = _auth(client, "qr_outsider@test.com")
        resp = client.get(f"/api/quiz-results/{result_id}", headers=headers_outsider)
        assert resp.status_code == 404


# ── Delete Tests ─────────────────────────────────────────────────

class TestDeleteQuizResult:
    def test_owner_delete_204(self, client, setup):
        headers = _auth(client, "qr_student@test.com")
        save_resp = client.post("/api/quiz-results/", json={
            "study_guide_id": setup["quiz_guide"].id,
            "score": 1,
            "total_questions": 2,
            "answers": {0: "A", 1: "C"},
        }, headers=headers)
        result_id = save_resp.json()["id"]
        resp = client.delete(f"/api/quiz-results/{result_id}", headers=headers)
        assert resp.status_code == 204
        # Verify gone
        resp2 = client.get(f"/api/quiz-results/{result_id}", headers=headers)
        assert resp2.status_code == 404

    def test_non_owner_delete_404(self, client, setup):
        headers_student = _auth(client, "qr_student@test.com")
        save_resp = client.post("/api/quiz-results/", json={
            "study_guide_id": setup["quiz_guide"].id,
            "score": 1,
            "total_questions": 2,
            "answers": {0: "A", 1: "C"},
        }, headers=headers_student)
        result_id = save_resp.json()["id"]
        headers_outsider = _auth(client, "qr_outsider@test.com")
        resp = client.delete(f"/api/quiz-results/{result_id}", headers=headers_outsider)
        assert resp.status_code == 404
