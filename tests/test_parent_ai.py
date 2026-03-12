"""Tests for Responsible AI Parent Tools endpoints (/api/parent-ai/*)."""
import json

import pytest
from unittest.mock import patch, AsyncMock
from conftest import PASSWORD, _auth


@pytest.fixture()
def pai_data(db_session):
    """Set up parent, student, course, assignments, quizzes for parent-ai tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole
    from app.models.student import Student, parent_students, RelationshipType
    from app.models.teacher import Teacher
    from app.models.course import Course, student_courses
    from app.models.assignment import Assignment, StudentAssignment
    from app.models.study_guide import StudyGuide
    from app.models.quiz_result import QuizResult
    from sqlalchemy import insert
    from datetime import datetime, timezone

    # Check if already created (session-scoped DB)
    parent = db_session.query(User).filter(User.email == "pai_parent@test.com").first()
    if parent:
        student_user = db_session.query(User).filter(User.email == "pai_student@test.com").first()
        outsider = db_session.query(User).filter(User.email == "pai_outsider@test.com").first()
        teacher_user = db_session.query(User).filter(User.email == "pai_teacher@test.com").first()
        student_rec = db_session.query(Student).filter(Student.user_id == student_user.id).first()
        course = db_session.query(Course).filter(Course.name == "PAI Test Course").first()
        assignment = db_session.query(Assignment).filter(Assignment.title == "PAI Test Assignment").first()
        return {
            "parent": parent,
            "student_user": student_user,
            "outsider": outsider,
            "teacher_user": teacher_user,
            "student_rec": student_rec,
            "course": course,
            "assignment": assignment,
        }

    hashed = get_password_hash(PASSWORD)
    parent = User(email="pai_parent@test.com", full_name="PAI Parent", role=UserRole.PARENT, hashed_password=hashed)
    student_user = User(email="pai_student@test.com", full_name="PAI Student", role=UserRole.STUDENT, hashed_password=hashed)
    outsider = User(email="pai_outsider@test.com", full_name="PAI Outsider", role=UserRole.PARENT, hashed_password=hashed)
    teacher_user = User(email="pai_teacher@test.com", full_name="PAI Teacher", role=UserRole.TEACHER, hashed_password=hashed)
    db_session.add_all([parent, student_user, outsider, teacher_user])
    db_session.flush()

    student_rec = Student(user_id=student_user.id, grade_level="8")
    teacher_rec = Teacher(user_id=teacher_user.id)
    db_session.add_all([student_rec, teacher_rec])
    db_session.flush()

    # Link parent -> student
    db_session.execute(insert(parent_students).values(
        parent_id=parent.id, student_id=student_rec.id,
        relationship_type=RelationshipType.GUARDIAN,
    ))

    # Course + enroll student
    course = Course(name="PAI Test Course", teacher_id=teacher_rec.id,
                    created_by_user_id=teacher_user.id, is_private=False)
    db_session.add(course)
    db_session.flush()
    db_session.execute(student_courses.insert().values(
        student_id=student_rec.id, course_id=course.id,
    ))

    # Assignment
    assignment = Assignment(title="PAI Test Assignment", course_id=course.id)
    db_session.add(assignment)
    db_session.flush()

    # Study guide linked to assignment
    guide = StudyGuide(
        user_id=student_user.id, title="PAI Guide", content="# Content",
        guide_type="study_guide", version=1, course_id=course.id,
        assignment_id=assignment.id,
    )
    db_session.add(guide)
    db_session.flush()

    # Quiz result
    quiz_result = QuizResult(
        user_id=student_user.id,
        study_guide_id=guide.id,
        score=3,
        total_questions=5,
        percentage=60.0,
        answers_json='{"0":"A","1":"B","2":"A","3":"C","4":"B"}',
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(quiz_result)

    # StudentAssignment (graded)
    sa = StudentAssignment(
        student_id=student_rec.id,
        assignment_id=assignment.id,
        grade=75.0,
        status="graded",
    )
    db_session.add(sa)

    db_session.commit()

    for u in [parent, student_user, outsider, teacher_user]:
        db_session.refresh(u)
    db_session.refresh(student_rec)
    db_session.refresh(course)
    db_session.refresh(assignment)

    return {
        "parent": parent,
        "student_user": student_user,
        "outsider": outsider,
        "teacher_user": teacher_user,
        "student_rec": student_rec,
        "course": course,
        "assignment": assignment,
    }


# ── Auth Tests ──────────────────────────────────────────────────

class TestParentAIAuth:
    """Only parents should access parent-ai endpoints."""

    def test_unauthenticated_gets_401(self, client):
        resp = client.post("/api/parent-ai/weak-spots", json={"student_id": 1})
        assert resp.status_code == 401

    def test_student_gets_403(self, client, pai_data):
        headers = _auth(client, pai_data["student_user"].email)
        resp = client.post("/api/parent-ai/weak-spots",
                           json={"student_id": pai_data["student_rec"].id},
                           headers=headers)
        assert resp.status_code == 403

    def test_teacher_gets_403(self, client, pai_data):
        headers = _auth(client, pai_data["teacher_user"].email)
        resp = client.post("/api/parent-ai/readiness-check",
                           json={"student_id": pai_data["student_rec"].id,
                                 "assignment_id": pai_data["assignment"].id},
                           headers=headers)
        assert resp.status_code == 403

    def test_student_blocked_from_practice_problems(self, client, pai_data):
        headers = _auth(client, pai_data["student_user"].email)
        resp = client.post("/api/parent-ai/practice-problems",
                           json={"student_id": pai_data["student_rec"].id,
                                 "course_id": pai_data["course"].id,
                                 "topic": "Algebra"},
                           headers=headers)
        assert resp.status_code == 403


# ── Weak Spots ──────────────────────────────────────────────────

class TestWeakSpots:

    def test_unlinked_child_returns_404(self, client, pai_data):
        """Outsider parent who doesn't own the child gets 404."""
        headers = _auth(client, pai_data["outsider"].email)
        resp = client.post("/api/parent-ai/weak-spots",
                           json={"student_id": pai_data["student_rec"].id},
                           headers=headers)
        assert resp.status_code == 404
        assert "not linked" in resp.json()["detail"].lower() or "not found" in resp.json()["detail"].lower()

    def test_empty_weak_spots_when_no_data(self, client, pai_data, db_session):
        """When filtering by a course with no quiz data, returns empty."""
        from app.models.course import Course
        from app.models.teacher import Teacher

        teacher_rec = db_session.query(Teacher).filter(Teacher.user_id == pai_data["teacher_user"].id).first()
        empty_course = Course(name="PAI Empty Course", teacher_id=teacher_rec.id,
                              created_by_user_id=pai_data["teacher_user"].id, is_private=False)
        db_session.add(empty_course)
        db_session.commit()
        db_session.refresh(empty_course)

        headers = _auth(client, pai_data["parent"].email)
        resp = client.post("/api/parent-ai/weak-spots",
                           json={"student_id": pai_data["student_rec"].id,
                                 "course_id": empty_course.id},
                           headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["weak_spots"] == []
        assert data["total_quizzes_analyzed"] == 0
        assert data["total_assignments_analyzed"] == 0
        assert "no quiz results" in data["summary"].lower() or "no quiz" in data["summary"].lower()

    def test_successful_weak_spots_with_mock_ai(self, client, pai_data):
        """Successful generation with AI mock returns parsed weak spots."""
        ai_response = json.dumps({
            "summary": "Student struggles with fractions.",
            "weak_spots": [
                {
                    "topic": "Fractions",
                    "severity": "high",
                    "detail": "Consistently below 60%",
                    "quiz_score_summary": "2/3 quizzes below 60%",
                    "suggested_action": "Practice fraction word problems",
                }
            ],
        })

        headers = _auth(client, pai_data["parent"].email)
        with patch(
            "app.api.routes.parent_ai.generate_content",
            new_callable=AsyncMock,
            return_value=(ai_response, "end_turn"),
        ), patch(
            "app.api.routes.parent_ai.increment_ai_usage",
        ) as mock_increment:
            resp = client.post("/api/parent-ai/weak-spots",
                               json={"student_id": pai_data["student_rec"].id},
                               headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["student_name"] == "PAI Student"
        assert len(data["weak_spots"]) == 1
        assert data["weak_spots"][0]["topic"] == "Fractions"
        assert data["weak_spots"][0]["severity"] == "high"
        assert data["total_quizzes_analyzed"] >= 1
        mock_increment.assert_called_once()

    def test_weak_spots_with_course_filter(self, client, pai_data):
        """Filtering by course_id returns course_name in response."""
        ai_response = json.dumps({"summary": "All good!", "weak_spots": []})
        headers = _auth(client, pai_data["parent"].email)
        with patch(
            "app.api.routes.parent_ai.generate_content",
            new_callable=AsyncMock,
            return_value=(ai_response, "end_turn"),
        ), patch("app.api.routes.parent_ai.increment_ai_usage"):
            resp = client.post("/api/parent-ai/weak-spots",
                               json={"student_id": pai_data["student_rec"].id,
                                     "course_id": pai_data["course"].id},
                               headers=headers)
        assert resp.status_code == 200
        assert resp.json()["course_name"] == "PAI Test Course"

    def test_weak_spots_malformed_ai_response(self, client, pai_data):
        """Malformed AI response still returns 200 with empty weak_spots."""
        headers = _auth(client, pai_data["parent"].email)
        with patch(
            "app.api.routes.parent_ai.generate_content",
            new_callable=AsyncMock,
            return_value=("This is not JSON at all", "end_turn"),
        ), patch("app.api.routes.parent_ai.increment_ai_usage"):
            resp = client.post("/api/parent-ai/weak-spots",
                               json={"student_id": pai_data["student_rec"].id},
                               headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["weak_spots"] == []
        assert "This is not JSON" in data["summary"]

    def test_weak_spots_ai_credit_check_blocks_at_limit(self, client, pai_data, db_session):
        """If user is at AI credit limit, returns 429."""
        parent = pai_data["parent"]
        parent.ai_usage_limit = 5
        parent.ai_usage_count = 5
        db_session.commit()

        headers = _auth(client, parent.email)
        resp = client.post("/api/parent-ai/weak-spots",
                           json={"student_id": pai_data["student_rec"].id},
                           headers=headers)
        assert resp.status_code == 429

        # Reset
        parent.ai_usage_limit = 0
        parent.ai_usage_count = 0
        db_session.commit()


# ── Readiness Check ─────────────────────────────────────────────

class TestReadinessCheck:

    def test_unlinked_child_returns_404(self, client, pai_data):
        headers = _auth(client, pai_data["outsider"].email)
        resp = client.post("/api/parent-ai/readiness-check",
                           json={"student_id": pai_data["student_rec"].id,
                                 "assignment_id": pai_data["assignment"].id},
                           headers=headers)
        assert resp.status_code == 404

    def test_nonexistent_assignment_returns_404(self, client, pai_data):
        headers = _auth(client, pai_data["parent"].email)
        resp = client.post("/api/parent-ai/readiness-check",
                           json={"student_id": pai_data["student_rec"].id,
                                 "assignment_id": 999999},
                           headers=headers)
        assert resp.status_code == 404
        assert "assignment not found" in resp.json()["detail"].lower()

    def test_readiness_with_study_activity(self, client, pai_data):
        """Student with study guide + quiz + graded assignment should score > 1."""
        headers = _auth(client, pai_data["parent"].email)
        resp = client.post("/api/parent-ai/readiness-check",
                           json={"student_id": pai_data["student_rec"].id,
                                 "assignment_id": pai_data["assignment"].id},
                           headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["student_name"] == "PAI Student"
        assert data["assignment_title"] == "PAI Test Assignment"
        assert data["course_name"] == "PAI Test Course"
        assert 1 <= data["readiness_score"] <= 5
        assert len(data["items"]) == 4
        assert data["readiness_score"] >= 3

    def test_readiness_no_activity(self, client, pai_data, db_session):
        """Fresh assignment with no activity scores 1."""
        from app.models.assignment import Assignment

        assignment2 = Assignment(title="PAI Fresh Assignment", course_id=pai_data["course"].id)
        db_session.add(assignment2)
        db_session.commit()
        db_session.refresh(assignment2)

        headers = _auth(client, pai_data["parent"].email)
        resp = client.post("/api/parent-ai/readiness-check",
                           json={"student_id": pai_data["student_rec"].id,
                                 "assignment_id": assignment2.id},
                           headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["readiness_score"] == 1
        assert "hasn't started" in data["summary"].lower()
        assert all(item["status"] == "missing" for item in data["items"])

    def test_readiness_no_ai_credits_used(self, client, pai_data):
        """Readiness check is pure SQL -- no AI mocking needed, no credit deduction."""
        headers = _auth(client, pai_data["parent"].email)
        with patch("app.api.routes.parent_ai.increment_ai_usage") as mock_inc:
            resp = client.post("/api/parent-ai/readiness-check",
                               json={"student_id": pai_data["student_rec"].id,
                                     "assignment_id": pai_data["assignment"].id},
                               headers=headers)
        assert resp.status_code == 200
        mock_inc.assert_not_called()


# ── Practice Problems ───────────────────────────────────────────

class TestPracticeProblems:

    def test_unlinked_child_returns_404(self, client, pai_data):
        headers = _auth(client, pai_data["outsider"].email)
        resp = client.post("/api/parent-ai/practice-problems",
                           json={"student_id": pai_data["student_rec"].id,
                                 "course_id": pai_data["course"].id,
                                 "topic": "Algebra"},
                           headers=headers)
        assert resp.status_code == 404

    def test_student_not_enrolled_returns_404(self, client, pai_data, db_session):
        """If student isn't enrolled in the course, returns 404."""
        from app.models.course import Course
        from app.models.teacher import Teacher

        teacher_rec = db_session.query(Teacher).filter(Teacher.user_id == pai_data["teacher_user"].id).first()
        other_course = Course(name="PAI Other Course", teacher_id=teacher_rec.id,
                              created_by_user_id=pai_data["teacher_user"].id, is_private=False)
        db_session.add(other_course)
        db_session.commit()
        db_session.refresh(other_course)

        headers = _auth(client, pai_data["parent"].email)
        with patch("app.api.routes.parent_ai.check_ai_usage"):
            resp = client.post("/api/parent-ai/practice-problems",
                               json={"student_id": pai_data["student_rec"].id,
                                     "course_id": other_course.id,
                                     "topic": "Algebra"},
                               headers=headers)
        assert resp.status_code == 404
        assert "not enrolled" in resp.json()["detail"].lower()

    def test_successful_practice_problems(self, client, pai_data):
        """Successful generation returns parsed problems."""
        ai_response = json.dumps({
            "problems": [
                {"number": 1, "question": "What is 2+2?", "hint": "Count on fingers"},
                {"number": 2, "question": "Simplify 4/8", "hint": "Find common factor"},
            ],
            "instructions": "Work through each problem carefully.",
        })

        headers = _auth(client, pai_data["parent"].email)
        with patch(
            "app.api.routes.parent_ai.generate_content",
            new_callable=AsyncMock,
            return_value=(ai_response, "end_turn"),
        ), patch(
            "app.api.routes.parent_ai.increment_ai_usage",
        ) as mock_increment:
            resp = client.post("/api/parent-ai/practice-problems",
                               json={"student_id": pai_data["student_rec"].id,
                                     "course_id": pai_data["course"].id,
                                     "topic": "Fractions"},
                               headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["student_name"] == "PAI Student"
        assert data["course_name"] == "PAI Test Course"
        assert data["topic"] == "Fractions"
        assert len(data["problems"]) == 2
        assert data["problems"][0]["question"] == "What is 2+2?"
        assert data["problems"][0]["hint"] == "Count on fingers"
        assert data["instructions"] == "Work through each problem carefully."
        mock_increment.assert_called_once()

    def test_practice_problems_malformed_ai_returns_502(self, client, pai_data):
        """Malformed AI response raises 502."""
        headers = _auth(client, pai_data["parent"].email)
        with patch(
            "app.api.routes.parent_ai.generate_content",
            new_callable=AsyncMock,
            return_value=("not json", "end_turn"),
        ), patch("app.api.routes.parent_ai.increment_ai_usage"):
            resp = client.post("/api/parent-ai/practice-problems",
                               json={"student_id": pai_data["student_rec"].id,
                                     "course_id": pai_data["course"].id,
                                     "topic": "Algebra"},
                               headers=headers)
        assert resp.status_code == 502

    def test_practice_problems_ai_credit_check(self, client, pai_data, db_session):
        """At credit limit, returns 429 before calling AI."""
        parent = pai_data["parent"]
        parent.ai_usage_limit = 1
        parent.ai_usage_count = 1
        db_session.commit()

        headers = _auth(client, parent.email)
        resp = client.post("/api/parent-ai/practice-problems",
                           json={"student_id": pai_data["student_rec"].id,
                                 "course_id": pai_data["course"].id,
                                 "topic": "Algebra"},
                           headers=headers)
        assert resp.status_code == 429

        # Reset
        parent.ai_usage_limit = 0
        parent.ai_usage_count = 0
        db_session.commit()

    def test_practice_problems_empty_topic_rejected(self, client, pai_data):
        """Empty topic string should be rejected by validation."""
        headers = _auth(client, pai_data["parent"].email)
        resp = client.post("/api/parent-ai/practice-problems",
                           json={"student_id": pai_data["student_rec"].id,
                                 "course_id": pai_data["course"].id,
                                 "topic": ""},
                           headers=headers)
        assert resp.status_code == 422
