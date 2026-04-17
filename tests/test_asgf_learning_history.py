"""Tests for ASGF learning history intelligence (#3403)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from conftest import PASSWORD, _auth


# ── Fixtures ──


@pytest.fixture()
def parent_user(db_session):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    email = f"lh_parent_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="LH Parent",
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

    email = f"lh_student_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="LH Student",
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
def weak_history(db_session, student):
    """Create a learning_history row with a weak score, 3 days old."""
    from app.models.learning_history import LearningHistory

    row = LearningHistory(
        student_id=student.id,
        session_id=uuid4().hex,
        session_type="asgf",
        question_asked="What is Newton's Third Law?",
        subject="Science",
        grade_level="Grade 9",
        overall_score_pct=50,
        weak_concepts=["action-reaction pairs", "force diagrams"],
        quiz_results=[
            {"question_text": "What is Newton's Third Law?", "correct": True, "attempts": 1, "xp_earned": 10},
            {"question_text": "Draw a force diagram", "correct": False, "attempts": 2, "xp_earned": 0},
        ],
        topic_tags=["Newton's Third Law"],
    )
    # Backdate created_at to 3 days ago
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    # Manually update created_at (server_default already set it to now)
    from sqlalchemy import text
    three_days_ago = datetime.now(timezone.utc) - timedelta(days=3)
    db_session.execute(
        text("UPDATE learning_history SET created_at = :dt WHERE id = :id"),
        {"dt": three_days_ago, "id": row.id},
    )
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.fixture()
def strong_history(db_session, student):
    """Create a learning_history row with a strong score (no review needed)."""
    from app.models.learning_history import LearningHistory

    row = LearningHistory(
        student_id=student.id,
        session_id=uuid4().hex,
        session_type="asgf",
        question_asked="What is photosynthesis?",
        subject="Biology",
        grade_level="Grade 9",
        overall_score_pct=90,
        topic_tags=["Photosynthesis"],
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


# ── Service unit tests ──


class TestGetSpacedRepetitionTopics:
    """Unit tests for get_spaced_repetition_topics."""

    @pytest.mark.asyncio
    async def test_returns_weak_topics_due_for_review(self, db_session, student, weak_history):
        from app.services.asgf_learning_history_service import get_spaced_repetition_topics

        topics = get_spaced_repetition_topics(student_id=student.id, db=db_session)
        assert len(topics) >= 1
        t = topics[0]
        assert t["subject"] == "Science"
        assert t["score_pct"] == 50
        assert t["days_since_last"] >= 3
        assert "weak_concepts" in t

    @pytest.mark.asyncio
    async def test_excludes_strong_scores(self, db_session, student, strong_history):
        from app.services.asgf_learning_history_service import get_spaced_repetition_topics

        topics = get_spaced_repetition_topics(student_id=student.id, db=db_session)
        subjects = [t["subject"] for t in topics]
        assert "Biology" not in subjects

    @pytest.mark.asyncio
    async def test_empty_for_no_history(self, db_session, student):
        from app.services.asgf_learning_history_service import get_spaced_repetition_topics

        topics = get_spaced_repetition_topics(student_id=student.id, db=db_session)
        assert topics == []


class TestGetAdaptiveContext:
    """Unit tests for get_adaptive_context."""

    @pytest.mark.asyncio
    async def test_returns_adaptive_context_for_repeat(self, db_session, student, weak_history):
        from app.services.asgf_learning_history_service import get_adaptive_context

        ctx = get_adaptive_context(student_id=student.id, topic="Newton", db=db_session)
        assert ctx["is_repeat"] is True
        assert ctx["session_count"] >= 1
        assert ctx["best_score"] == 50
        assert len(ctx["weak_concepts"]) > 0

    @pytest.mark.asyncio
    async def test_returns_not_repeat_for_new_topic(self, db_session, student, weak_history):
        from app.services.asgf_learning_history_service import get_adaptive_context

        ctx = get_adaptive_context(student_id=student.id, topic="Algebra", db=db_session)
        assert ctx["is_repeat"] is False
        assert ctx["session_count"] == 0

    @pytest.mark.asyncio
    async def test_mastered_concepts_from_correct_answers(self, db_session, student, weak_history):
        from app.services.asgf_learning_history_service import get_adaptive_context

        ctx = get_adaptive_context(student_id=student.id, topic="Newton's Third Law", db=db_session)
        # "What is Newton's Third Law?" was correct
        assert "What is Newton's Third Law?" in ctx["mastered_concepts"]
        # "Draw a force diagram" was incorrect
        assert "Draw a force diagram" in ctx["weak_concepts"]


class TestUpdateLearningHistoryOnComplete:
    """Unit tests for update_learning_history_on_complete."""

    @pytest.mark.asyncio
    async def test_updates_scores(self, db_session, student):
        from app.models.learning_history import LearningHistory
        from app.services.asgf_learning_history_service import update_learning_history_on_complete

        row = LearningHistory(
            student_id=student.id,
            session_id=uuid4().hex,
            session_type="asgf",
            question_asked="Test question",
            subject="Math",
        )
        db_session.add(row)
        db_session.commit()

        quiz = [
            {"question_text": "Q1", "correct": True, "attempts": 1, "xp_earned": 10},
            {"question_text": "Q2", "correct": False, "attempts": 3, "xp_earned": 0},
            {"question_text": "Q3", "correct": True, "attempts": 1, "xp_earned": 10},
            {"question_text": "Q4", "correct": True, "attempts": 2, "xp_earned": 5},
        ]
        update_learning_history_on_complete(
            session_id=row.session_id, quiz_results=quiz, db=db_session,
        )
        # Caller is responsible for commit (#3497)
        db_session.commit()

        db_session.refresh(row)
        assert row.overall_score_pct == 75  # 3/4
        assert row.avg_attempts_per_q == 1.75
        assert row.weak_concepts == ["Q2"]
        assert row.quiz_results == quiz

    @pytest.mark.asyncio
    async def test_no_op_for_missing_session(self, db_session):
        from app.services.asgf_learning_history_service import update_learning_history_on_complete

        # Should not raise
        update_learning_history_on_complete(
            session_id="nonexistent", quiz_results=[], db=db_session,
        )


# ── API endpoint tests ──


class TestReviewTopicsEndpoint:
    """GET /api/asgf/student/{student_id}/review-topics"""

    def test_parent_gets_review_topics(
        self, client, db_session, linked_parent, student, weak_history
    ):
        headers = _auth(client, linked_parent.email)
        resp = client.get(
            f"/api/asgf/student/{student.id}/review-topics",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["student_id"] == student.id
        assert isinstance(data["topics"], list)

    def test_student_gets_own_review_topics(
        self, client, db_session, student_user, student, weak_history
    ):
        headers = _auth(client, student_user.email)
        resp = client.get(
            f"/api/asgf/student/{student.id}/review-topics",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

    def test_unrelated_parent_gets_404(
        self, client, db_session, student, weak_history
    ):
        from app.core.security import get_password_hash
        from app.models.user import User, UserRole

        other = User(
            email=f"lh_other_{uuid4().hex[:8]}@test.com",
            full_name="Other Parent",
            role=UserRole.PARENT,
            hashed_password=get_password_hash(PASSWORD),
        )
        db_session.add(other)
        db_session.commit()

        headers = _auth(client, other.email)
        resp = client.get(
            f"/api/asgf/student/{student.id}/review-topics",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_401_without_auth(self, client):
        resp = client.get("/api/asgf/student/1/review-topics")
        assert resp.status_code == 401

    def test_empty_when_no_weak_topics(
        self, client, db_session, linked_parent, student, strong_history
    ):
        headers = _auth(client, linked_parent.email)
        resp = client.get(
            f"/api/asgf/student/{student.id}/review-topics",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["topics"] == []


class TestAdaptiveContextWiring:
    """Verify adaptive context is wired into assemble_context_package."""

    @pytest.mark.asyncio
    async def test_adaptive_context_enriches_gap_data(self):
        from app.services.asgf_service import assemble_context_package
        from app.schemas.asgf import IntentClassifyResponse

        adaptive = {
            "is_repeat": True,
            "mastered_concepts": ["concept A"],
            "weak_concepts": ["concept B"],
            "session_count": 2,
            "best_score": 60,
        }

        intent = IntentClassifyResponse(
            subject="Math", grade_level="Grade 9", topic="Algebra",
        )

        pkg = await assemble_context_package(
            question="What is algebra?",
            ingestion_result={"concepts": [], "gap_data": {}, "document_metadata": []},
            adaptive_context=adaptive,
            intent_result=intent,
        )

        assert "concept B" in pkg.gap_data.weak_topics
        assert "concept A" in pkg.gap_data.previously_studied
        assert pkg.session_metadata.get("is_repeat_session") is True
        assert pkg.session_metadata.get("prior_session_count") == 2
        assert pkg.session_metadata.get("best_prior_score") == 60

    @pytest.mark.asyncio
    async def test_no_adaptive_context_leaves_gap_empty(self):
        from app.services.asgf_service import assemble_context_package
        from app.schemas.asgf import IntentClassifyResponse

        intent = IntentClassifyResponse(
            subject="Math", grade_level="Grade 9", topic="Algebra",
        )

        pkg = await assemble_context_package(
            question="What is algebra?",
            ingestion_result={"concepts": [], "gap_data": {}, "document_metadata": []},
            intent_result=intent,
        )

        assert pkg.gap_data.weak_topics == []
        assert pkg.gap_data.previously_studied == []
        assert "is_repeat_session" not in pkg.session_metadata
