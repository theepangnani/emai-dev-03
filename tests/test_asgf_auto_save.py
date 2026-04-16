"""Tests for ASGF session completion / auto-save (#3401)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Fixtures ──


@pytest.fixture()
def parent_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = f"asgf_parent_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="Test Parent",
        role=UserRole.PARENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def student_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = f"asgf_student_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="Haashini",
        role=UserRole.STUDENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def student(db_session, student_user):
    from app.models.student import Student

    s = Student(user_id=student_user.id, grade_level=9)
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


@pytest.fixture()
def linked_parent(db_session, parent_user, student):
    """Link the parent to the student."""
    from app.models.student import parent_students

    db_session.execute(
        parent_students.insert().values(
            parent_id=parent_user.id,
            student_id=student.id,
        )
    )
    db_session.commit()
    return parent_user


@pytest.fixture()
def session_id():
    return uuid4().hex


@pytest.fixture()
def learning_history(db_session, student, session_id):
    from app.models.learning_history import LearningHistory

    row = LearningHistory(
        student_id=student.id,
        session_id=session_id,
        session_type="asgf",
        question_asked="What is Newton's Third Law?",
        subject="Science",
        grade_level="Grade 9",
        slides_generated=[
            {"slide_number": 0, "title": "Introduction", "body": "Every action has an equal and opposite reaction."},
            {"slide_number": 1, "title": "Examples", "body": "Rockets push exhaust down, thrust goes up."},
        ],
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


QUIZ_RESULTS = [
    {"question_text": "What is Newton's Third Law?", "correct": True, "attempts": 1, "xp_earned": 10},
    {"question_text": "Which is an example of the third law?", "correct": True, "attempts": 1, "xp_earned": 10},
    {"question_text": "What happens when you push a wall?", "correct": False, "attempts": 2, "xp_earned": 0},
    {"question_text": "Is gravity a third-law pair?", "correct": True, "attempts": 1, "xp_earned": 10},
    {"question_text": "Explain action-reaction in swimming", "correct": True, "attempts": 2, "xp_earned": 5},
]


# ── Tests ──


class TestCompleteSession:
    """POST /api/asgf/session/{session_id}/complete"""

    @patch("app.services.asgf_save_service.get_async_anthropic_client")
    def test_parent_completes_session(
        self, mock_client, client, db_session, linked_parent, student, learning_history, session_id
    ):
        # Mock the Anthropic API response for summary generation
        mock_response = AsyncMock()
        mock_response.content = [AsyncMock(text="Haashini completed a Flash Study on Newton's Third Law. She answered 4 of 5 correctly.")]
        mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

        headers = _auth(client, linked_parent.email)
        resp = client.post(
            f"/api/asgf/session/{session_id}/complete",
            json={"quiz_results": QUIZ_RESULTS},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "material_id" in data
        assert "summary" in data
        assert data["material_id"] > 0

        # Verify StudyGuide was created
        from app.models.study_guide import StudyGuide
        sg = db_session.query(StudyGuide).filter(StudyGuide.id == data["material_id"]).first()
        assert sg is not None
        assert sg.guide_type == "study_guide"
        assert "Newton's Third Law" in sg.title

        # Verify learning_history was updated
        db_session.refresh(learning_history)
        assert learning_history.material_id == data["material_id"]
        assert learning_history.overall_score_pct == 80  # 4/5
        assert learning_history.quiz_results is not None

    @patch("app.services.asgf_save_service.get_async_anthropic_client")
    def test_student_completes_own_session(
        self, mock_client, client, db_session, student_user, student, learning_history, session_id
    ):
        mock_response = AsyncMock()
        mock_response.content = [AsyncMock(text="Summary text.")]
        mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

        headers = _auth(client, student_user.email)
        resp = client.post(
            f"/api/asgf/session/{session_id}/complete",
            json={"quiz_results": QUIZ_RESULTS},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["material_id"] > 0

    def test_404_for_unknown_session(self, client, db_session, linked_parent):
        headers = _auth(client, linked_parent.email)
        resp = client.post(
            "/api/asgf/session/nonexistent123/complete",
            json={"quiz_results": QUIZ_RESULTS},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_401_without_auth(self, client):
        resp = client.post(
            "/api/asgf/session/abc/complete",
            json={"quiz_results": QUIZ_RESULTS},
        )
        assert resp.status_code == 401

    def test_422_empty_quiz_results(self, client, db_session, linked_parent, learning_history, session_id):
        headers = _auth(client, linked_parent.email)
        resp = client.post(
            f"/api/asgf/session/{session_id}/complete",
            json={"quiz_results": []},
            headers=headers,
        )
        assert resp.status_code == 422

    @patch("app.services.asgf_save_service.get_async_anthropic_client")
    def test_idempotent_completion(
        self, mock_client, client, db_session, linked_parent, student, learning_history, session_id
    ):
        """Completing the same session twice returns the same material_id."""
        mock_response = AsyncMock()
        mock_response.content = [AsyncMock(text="Summary.")]
        mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

        headers = _auth(client, linked_parent.email)

        # First completion
        resp1 = client.post(
            f"/api/asgf/session/{session_id}/complete",
            json={"quiz_results": QUIZ_RESULTS},
            headers=headers,
        )
        assert resp1.status_code == 200
        material_id = resp1.json()["material_id"]

        # Second completion — should be idempotent
        resp2 = client.post(
            f"/api/asgf/session/{session_id}/complete",
            json={"quiz_results": QUIZ_RESULTS},
            headers=headers,
        )
        assert resp2.status_code == 200
        assert resp2.json()["material_id"] == material_id

    def test_unrelated_parent_cannot_complete(self, client, db_session, student, learning_history, session_id):
        """A parent not linked to the student cannot complete their session."""
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        other_parent = User(
            email=f"asgf_other_{uuid4().hex[:8]}@test.com",
            full_name="Other Parent",
            role=UserRole.PARENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(other_parent)
        db_session.commit()

        headers = _auth(client, other_parent.email)
        resp = client.post(
            f"/api/asgf/session/{session_id}/complete",
            json={"quiz_results": QUIZ_RESULTS},
            headers=headers,
        )
        assert resp.status_code == 404


class TestAutoSaveService:
    """Unit tests for asgf_save_service.auto_save_session."""

    @pytest.mark.asyncio
    @patch("app.services.asgf_save_service.get_async_anthropic_client")
    async def test_auto_save_creates_study_guide(
        self, mock_client, db_session, student, learning_history, session_id
    ):
        from app.services.asgf_save_service import auto_save_session

        mock_response = AsyncMock()
        mock_response.content = [AsyncMock(text="Great session on Newton's Third Law.")]
        mock_client.return_value.messages.create = AsyncMock(return_value=mock_response)

        slides = [
            {"title": "Intro", "body": "Content here"},
            {"title": "Examples", "body": "More content"},
        ]
        quiz = [
            {"question_text": "Q1", "correct": True, "attempts": 1, "xp_earned": 10},
            {"question_text": "Q2", "correct": False, "attempts": 2, "xp_earned": 0},
        ]

        material_id, summary = await auto_save_session(
            session_id=session_id,
            slides=slides,
            quiz_results=quiz,
            student_id=student.id,
            db=db_session,
        )

        assert material_id > 0
        assert len(summary) > 0

        # Verify DB state
        from app.models.study_guide import StudyGuide
        sg = db_session.query(StudyGuide).filter(StudyGuide.id == material_id).first()
        assert sg is not None
        assert sg.guide_type == "study_guide"
        assert sg.user_id == student.user_id

        db_session.refresh(learning_history)
        assert learning_history.material_id == material_id
        assert learning_history.overall_score_pct == 50
        assert learning_history.avg_attempts_per_q == 1.5

    @pytest.mark.asyncio
    async def test_auto_save_raises_for_missing_session(self, db_session, student):
        from app.services.asgf_save_service import auto_save_session

        with pytest.raises(ValueError, match="not found"):
            await auto_save_session(
                session_id="nonexistent",
                slides=[],
                quiz_results=[],
                student_id=student.id,
                db=db_session,
            )
