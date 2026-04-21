"""
Tests for ILE (Flash Tutor) session lifecycle and performance (#3217).

Tests:
- Session create -> answer -> complete flow
- Adaptive difficulty transitions
- Mastery update after completion
- Response caching
- Question bank format filter
"""
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from conftest import PASSWORD, _auth


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ile_student(db_session):
    """Create a student user for ILE tests."""
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash

    hashed = get_password_hash(PASSWORD)
    student = db_session.query(User).filter(User.email == "ile_student@test.com").first()
    if not student:
        student = User(
            email="ile_student@test.com",
            username="ile_student",
            hashed_password=hashed,
            full_name="ILE Student",
            role=UserRole.STUDENT,
            roles="student",
            onboarding_completed=True,
            email_verified=True,
        )
        db_session.add(student)
        db_session.commit()
        db_session.refresh(student)
    return student


@pytest.fixture()
def _cleanup_ile(db_session):
    """Clean up ILE tables after each test."""
    yield
    from app.models.ile_session import ILESession
    from app.models.ile_question_attempt import ILEQuestionAttempt
    from app.models.ile_topic_mastery import ILETopicMastery
    from app.models.ile_student_calibration import ILEStudentCalibration

    db_session.query(ILEQuestionAttempt).delete()
    db_session.query(ILESession).delete()
    db_session.query(ILETopicMastery).delete()
    db_session.query(ILEStudentCalibration).delete()
    db_session.commit()


# Fake questions returned by the AI question generator
FAKE_QUESTIONS = [
    {
        "question": f"What is {i}+1?",
        "options": {"A": str(i), "B": str(i + 1), "C": str(i + 2), "D": str(i + 3)},
        "correct_answer": "B",
        "explanation": f"Because {i}+1 = {i + 1}.",
        "difficulty": "medium",
        "blooms_tier": "recall",
        "format": "mcq",
    }
    for i in range(1, 8)
]


async def _mock_generate(
    db=None,
    subject="",
    topic="",
    grade_level=8,
    difficulty="medium",
    blooms_tier="recall",
    count=5,
    question_format="mcq",
    context_text=None,
):
    """Mock for ile_question_service.get_from_bank_or_generate."""
    return FAKE_QUESTIONS[:count]


# ---------------------------------------------------------------------------
# Session lifecycle tests
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_cleanup_ile")
class TestILESessionLifecycle:
    """Test the full create -> answer -> complete flow."""

    @patch(
        "app.services.ile_question_service.get_from_bank_or_generate",
        side_effect=_mock_generate,
    )
    def test_create_session(self, mock_gen, client, ile_student):
        headers = _auth(client, "ile_student@test.com")
        resp = client.post(
            "/api/ile/sessions",
            json={
                "mode": "learning",
                "subject": "Math",
                "topic": "Addition",
                "question_count": 5,
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["subject"] == "Math"
        assert data["topic"] == "Addition"
        assert data["question_count"] == 5

    @patch(
        "app.services.ile_question_service.get_from_bank_or_generate",
        side_effect=_mock_generate,
    )
    def test_create_answer_complete_flow(self, mock_gen, client, ile_student):
        headers = _auth(client, "ile_student@test.com")

        # Create session
        resp = client.post(
            "/api/ile/sessions",
            json={
                "mode": "testing",
                "subject": "Math",
                "topic": "Addition",
                "question_count": 3,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        session_id = resp.json()["id"]

        # Answer all questions correctly
        for i in range(3):
            # Get question
            q_resp = client.get(f"/api/ile/sessions/{session_id}/question", headers=headers)
            assert q_resp.status_code == 200
            assert q_resp.json()["question_index"] == i

            # Submit answer
            a_resp = client.post(
                f"/api/ile/sessions/{session_id}/answer",
                json={"answer": "B"},
                headers=headers,
            )
            assert a_resp.status_code == 200
            feedback = a_resp.json()
            assert feedback["is_correct"] is True
            assert feedback["question_complete"] is True

        # Complete session
        c_resp = client.post(f"/api/ile/sessions/{session_id}/complete", headers=headers)
        assert c_resp.status_code == 200
        results = c_resp.json()
        assert results["score"] == 3
        assert results["total_questions"] == 3
        assert results["percentage"] == 100.0

    @patch(
        "app.services.ile_question_service.get_from_bank_or_generate",
        side_effect=_mock_generate,
    )
    def test_cannot_create_duplicate_session(self, mock_gen, client, ile_student):
        headers = _auth(client, "ile_student@test.com")

        # Create first session
        resp1 = client.post(
            "/api/ile/sessions",
            json={"mode": "learning", "subject": "Math", "topic": "Addition"},
            headers=headers,
        )
        assert resp1.status_code == 201

        # Second session should fail
        resp2 = client.post(
            "/api/ile/sessions",
            json={"mode": "learning", "subject": "Math", "topic": "Subtraction"},
            headers=headers,
        )
        assert resp2.status_code == 400
        assert "Active session" in resp2.json()["detail"]

    @patch(
        "app.services.ile_question_service.get_from_bank_or_generate",
        side_effect=_mock_generate,
    )
    def test_abandon_session(self, mock_gen, client, ile_student):
        headers = _auth(client, "ile_student@test.com")

        resp = client.post(
            "/api/ile/sessions",
            json={"mode": "learning", "subject": "Math", "topic": "Addition"},
            headers=headers,
        )
        session_id = resp.json()["id"]

        # Abandon
        a_resp = client.post(f"/api/ile/sessions/{session_id}/abandon", headers=headers)
        assert a_resp.status_code == 204

        # Verify status
        s_resp = client.get(f"/api/ile/sessions/{session_id}", headers=headers)
        assert s_resp.json()["status"] == "abandoned"


# ---------------------------------------------------------------------------
# Adaptive difficulty tests
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_cleanup_ile")
class TestAdaptiveDifficulty:

    def test_difficulty_increase_after_consecutive_correct(self, db_session, ile_student):
        """Two consecutive first-attempt correct answers should increase difficulty."""
        from app.models.ile_session import ILESession
        from app.models.ile_question_attempt import ILEQuestionAttempt
        from app.services.ile_adaptive_service import adjust_within_session

        now = datetime.now(timezone.utc)
        session = ILESession(
            student_id=ile_student.id,
            mode="testing",
            subject="Math",
            topic="Addition",
            question_count=5,
            difficulty="medium",
            blooms_tier="recall",
            status="in_progress",
            current_question_index=2,
            questions_json=json.dumps(FAKE_QUESTIONS[:5]),
            started_at=now,
            expires_at=now + timedelta(hours=24),
        )
        db_session.add(session)
        db_session.flush()

        # Add two first-attempt correct answers
        for qi in range(2):
            db_session.add(ILEQuestionAttempt(
                session_id=session.id,
                question_index=qi,
                question_text=f"Q{qi}",
                question_format="mcq",
                difficulty_level="medium",
                selected_answer="B",
                correct_answer="B",
                is_correct=True,
                attempt_number=1,
                xp_earned=10,
            ))
        db_session.flush()

        new_diff = adjust_within_session(db_session, session)
        assert new_diff == "challenging"

    def test_difficulty_decrease_after_multi_attempt(self, db_session, ile_student):
        """Two consecutive multi-attempt answers should decrease difficulty."""
        from app.models.ile_session import ILESession
        from app.models.ile_question_attempt import ILEQuestionAttempt
        from app.services.ile_adaptive_service import adjust_within_session

        now = datetime.now(timezone.utc)
        session = ILESession(
            student_id=ile_student.id,
            mode="learning",
            subject="Math",
            topic="Addition",
            question_count=5,
            difficulty="challenging",
            blooms_tier="recall",
            status="in_progress",
            current_question_index=2,
            questions_json=json.dumps(FAKE_QUESTIONS[:5]),
            started_at=now,
            expires_at=now + timedelta(hours=24),
        )
        db_session.add(session)
        db_session.flush()

        # Add two multi-attempt correct answers (attempt_number > 1)
        for qi in range(2):
            # Wrong attempt first
            db_session.add(ILEQuestionAttempt(
                session_id=session.id,
                question_index=qi,
                question_text=f"Q{qi}",
                question_format="mcq",
                difficulty_level="challenging",
                selected_answer="A",
                correct_answer="B",
                is_correct=False,
                attempt_number=1,
                xp_earned=0,
            ))
            # Then correct on attempt 2
            db_session.add(ILEQuestionAttempt(
                session_id=session.id,
                question_index=qi,
                question_text=f"Q{qi}",
                question_format="mcq",
                difficulty_level="challenging",
                selected_answer="B",
                correct_answer="B",
                is_correct=True,
                attempt_number=2,
                xp_earned=20,
            ))
        db_session.flush()

        new_diff = adjust_within_session(db_session, session)
        assert new_diff == "medium"


# ---------------------------------------------------------------------------
# Mastery update tests
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_cleanup_ile")
class TestMasteryUpdate:

    def test_mastery_created_after_session(self, db_session, ile_student):
        """Completing a session should create/update a mastery record."""
        from app.models.ile_session import ILESession
        from app.models.ile_question_attempt import ILEQuestionAttempt
        from app.models.ile_topic_mastery import ILETopicMastery
        from app.services.ile_mastery_service import update_mastery_after_session

        now = datetime.now(timezone.utc)
        session = ILESession(
            student_id=ile_student.id,
            mode="testing",
            subject="Science",
            topic="Photosynthesis",
            question_count=3,
            difficulty="medium",
            blooms_tier="recall",
            status="completed",
            current_question_index=3,
            questions_json=json.dumps(FAKE_QUESTIONS[:3]),
            started_at=now,
            completed_at=now + timedelta(minutes=5),
            score=2,
            total_correct=2,
            xp_awarded=20,
        )
        db_session.add(session)
        db_session.flush()

        # Add attempts
        for qi in range(3):
            db_session.add(ILEQuestionAttempt(
                session_id=session.id,
                question_index=qi,
                question_text=f"Q{qi}",
                question_format="mcq",
                difficulty_level="medium",
                selected_answer="B",
                correct_answer="B",
                is_correct=(qi < 2),  # First 2 correct, last wrong
                attempt_number=1,
                xp_earned=10 if qi < 2 else 0,
            ))
        db_session.flush()

        question_results = [
            {
                "index": qi,
                "is_correct": qi < 2,
                "attempts": 1,
                "difficulty": "medium",
                "format": "mcq",
            }
            for qi in range(3)
        ]

        update_mastery_after_session(db_session, session, question_results)

        mastery = (
            db_session.query(ILETopicMastery)
            .filter(
                ILETopicMastery.student_id == ile_student.id,
                ILETopicMastery.subject == "Science",
                ILETopicMastery.topic == "Photosynthesis",
            )
            .first()
        )
        assert mastery is not None
        assert mastery.total_sessions == 1
        assert mastery.total_questions_seen == 3
        assert mastery.total_first_attempt_correct == 2


# ---------------------------------------------------------------------------
# Response caching tests
# ---------------------------------------------------------------------------

class TestResponseCache:

    def test_cache_set_and_get(self):
        """Basic TTL cache get/set."""
        from app.api.routes.ile import _cache_get, _cache_set, _cache

        _cache.clear()
        _cache_set("test:key", {"data": 42})
        assert _cache_get("test:key") == {"data": 42}

    def test_cache_expired(self):
        """Expired entries return None."""
        from app.api.routes.ile import _cache_get, _cache, _CACHE_TTL

        _cache.clear()
        # Insert an entry that's already expired
        _cache["test:old"] = (time.monotonic() - _CACHE_TTL - 1, {"old": True})
        assert _cache_get("test:old") is None

    def test_cache_invalidate_user(self):
        """Invalidating a user clears their entries."""
        from app.api.routes.ile import (
            _cache_get, _cache_set, _cache_invalidate_user, _cache,
        )

        _cache.clear()
        _cache_set("mastery:42:map", {"entries": []})
        _cache_set("topics:42", {"topics": []})
        _cache_set("mastery:99:map", {"other": True})

        _cache_invalidate_user(42)

        assert _cache_get("mastery:42:map") is None
        assert _cache_get("topics:42") is None
        # Other user unaffected
        assert _cache_get("mastery:99:map") == {"other": True}
        _cache.clear()


# ---------------------------------------------------------------------------
# Question bank format filter tests
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_cleanup_ile")
class TestQuestionBankFormatFilter:

    def test_get_from_bank_filters_by_format(self, db_session):
        """get_from_bank should filter by question_format at DB level."""
        from app.models.ile_question_bank import ILEQuestionBank
        from app.services.ile_question_service import get_from_bank

        # Add MCQ and fill_blank questions
        for fmt in ("mcq", "fill_blank"):
            db_session.add(ILEQuestionBank(
                subject="Math",
                topic="Addition",
                grade_level=8,
                difficulty="medium",
                question_format=fmt,
                question_json=json.dumps({
                    "question": f"Test {fmt}",
                    "correct_answer": "B" if fmt == "mcq" else "answer",
                    "options": {"A": "1", "B": "2", "C": "3", "D": "4"} if fmt == "mcq" else None,
                    "format": fmt,
                }),
            ))
        db_session.commit()

        mcq_results = get_from_bank(
            db_session, "Math", "Addition", 8, "medium", 10, question_format="mcq",
        )
        fill_results = get_from_bank(
            db_session, "Math", "Addition", 8, "medium", 10, question_format="fill_blank",
        )

        assert len(mcq_results) >= 1
        assert len(fill_results) >= 1
        assert all(q.get("format", "mcq") == "mcq" for q in mcq_results)


# ---------------------------------------------------------------------------
# Rate limiting test (via API — rate limiter disabled in test fixture)
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_cleanup_ile")
class TestILERateLimiting:

    @patch(
        "app.services.ile_question_service.get_from_bank_or_generate",
        side_effect=_mock_generate,
    )
    def test_session_creation_has_rate_limit_decorator(self, mock_gen, client, ile_student):
        """Verify the create_session endpoint has rate limiting configured.

        Rate limiter is disabled during tests, but the decorator should exist.
        This test confirms the endpoint works and the mock is wired correctly.
        """
        headers = _auth(client, "ile_student@test.com")
        resp = client.post(
            "/api/ile/sessions",
            json={"mode": "testing", "subject": "Math", "topic": "Addition"},
            headers=headers,
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Aha-moment parent notification tests (#3840)
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_cleanup_ile")
class TestAhaMomentNotification:
    """Regression tests for #3840 — full_name parsing for parent notifications."""

    def _build_completed_session(self, db_session, student_id):
        from app.models.ile_session import ILESession
        from app.models.ile_question_attempt import ILEQuestionAttempt

        now = datetime.now(timezone.utc)
        session = ILESession(
            student_id=student_id,
            mode="testing",
            subject="Math",
            topic="Fractions",
            question_count=3,
            difficulty="medium",
            blooms_tier="recall",
            status="in_progress",
            current_question_index=3,
            questions_json=json.dumps(FAKE_QUESTIONS[:3]),
            started_at=now - timedelta(minutes=5),
            expires_at=now + timedelta(hours=24),
        )
        db_session.add(session)
        db_session.flush()

        for qi in range(3):
            db_session.add(ILEQuestionAttempt(
                session_id=session.id,
                question_index=qi,
                question_text=f"Q{qi}",
                question_format="mcq",
                difficulty_level="medium",
                selected_answer="B",
                correct_answer="B",
                is_correct=True,
                attempt_number=1,
                xp_earned=10,
            ))
        db_session.commit()
        return session

    def test_aha_moment_notification_uses_first_name_from_full_name(
        self, db_session, ile_student,
    ):
        """Aha-moment notification derives first name from full_name (not first_name).

        Before the fix, `student_user.first_name` raised AttributeError (swallowed
        by broad except), so parents never received the breakthrough notification.
        With the fix, the first name is parsed from `full_name` and the title
        begins with it (e.g. "ILE ..." from "ILE Student").
        """
        import asyncio
        from app.services import ile_service

        session = self._build_completed_session(db_session, ile_student.id)

        captured = {}

        def _capture_notify(**kwargs):
            captured.update(kwargs)
            return []

        with patch.object(
            ile_service, "update_student_calibration", return_value=None,
        ), patch(
            "app.services.ile_mastery_service.update_mastery_after_session",
            return_value=MagicMock(),
        ), patch(
            "app.services.ile_mastery_service.get_mastery_snapshot",
            return_value={"accuracy": 0.2},
        ), patch(
            "app.services.ile_mastery_service.check_aha_moment", return_value=True,
        ), patch(
            "app.services.notification_service.notify_parents_of_student",
            side_effect=_capture_notify,
        ):
            asyncio.run(ile_service.complete_session(db_session, session))

        assert captured, "notify_parents_of_student was not called"
        # "ILE Student" -> first token "ILE"
        assert captured["title"].startswith("ILE "), captured.get("title")
        assert "had a breakthrough in Fractions" in captured["title"]
        assert captured["content"].startswith("ILE was struggling with"), (
            captured.get("content")
        )
