"""Tests for ASGF cost logging and session cap enforcement (#3405)."""
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

    email = f"cost_parent_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="Cost Parent",
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

    email = f"cost_student_{uuid4().hex[:8]}@test.com"
    user = User(
        email=email,
        full_name="Cost Student",
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


# ── Service unit tests ──


@pytest.mark.asyncio
async def test_check_session_cap_no_sessions(db_session, student):
    """Cap check returns full capacity when no sessions exist."""
    from app.services.asgf_cost_service import check_session_cap

    result = check_session_cap(student.id, db_session)
    assert result["used"] == 0
    assert result["limit"] == 10
    assert result["remaining"] == 10
    assert result["can_start"] is True


@pytest.mark.asyncio
async def test_check_session_cap_at_limit(db_session, student):
    """Cap check blocks when the free-tier limit is reached."""
    from app.models.learning_history import LearningHistory
    from app.services.asgf_cost_service import ASGF_FREE_TIER_LIMIT, check_session_cap

    for i in range(ASGF_FREE_TIER_LIMIT):
        db_session.add(
            LearningHistory(
                student_id=student.id,
                session_id=uuid4().hex,
                session_type="asgf",
                question_asked=f"Q{i}",
            )
        )
    db_session.commit()

    result = check_session_cap(student.id, db_session)
    assert result["used"] == ASGF_FREE_TIER_LIMIT
    assert result["remaining"] == 0
    assert result["can_start"] is False


@pytest.mark.asyncio
async def test_log_asgf_cost(db_session, student_user):
    """log_asgf_cost persists a row to ai_usage_history."""
    from app.models.ai_usage_history import AIUsageHistory
    from app.services.asgf_cost_service import log_asgf_cost

    session_id = uuid4().hex
    log_asgf_cost(
        session_id=session_id,
        operation="asgf_plan",
        model="gpt-4o-mini",
        input_tokens=500,
        output_tokens=200,
        user_id=student_user.id,
        db=db_session,
    )

    row = (
        db_session.query(AIUsageHistory)
        .filter(
            AIUsageHistory.user_id == student_user.id,
            AIUsageHistory.generation_type == "asgf_plan",
        )
        .first()
    )
    assert row is not None
    assert row.prompt_tokens == 500
    assert row.completion_tokens == 200
    assert row.total_tokens == 700
    assert row.model_name == "gpt-4o-mini"
    assert row.estimated_cost_usd > 0


@pytest.mark.asyncio
async def test_get_monthly_cost_summary(db_session, student):
    """Monthly cost summary counts sessions correctly."""
    from app.models.learning_history import LearningHistory
    from app.services.asgf_cost_service import get_monthly_cost_summary

    for i in range(3):
        db_session.add(
            LearningHistory(
                student_id=student.id,
                session_id=uuid4().hex,
                session_type="asgf",
                question_asked=f"Q{i}",
            )
        )
    db_session.commit()

    result = get_monthly_cost_summary(student.id, db_session)
    assert result["session_count"] == 3
    assert "total_cost_usd" in result
    assert "total_tokens" in result


# ── API endpoint tests ──


def test_get_asgf_usage_student(client, db_session, student_user, student):
    """GET /api/asgf/usage returns cap info for a student user."""
    headers = _auth(client, student_user.email)
    resp = client.get("/api/asgf/usage", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["used"] == 0
    assert data["limit"] == 10
    assert data["can_start"] is True


def test_get_asgf_usage_parent(client, db_session, linked_parent, student):
    """GET /api/asgf/usage returns cap info for a parent's child."""
    headers = _auth(client, linked_parent.email)
    resp = client.get(f"/api/asgf/usage?child_id={student.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 10
    assert data["can_start"] is True


def test_create_session_blocked_at_cap(client, db_session, student_user, student):
    """POST /api/asgf/session returns 429 when the cap is reached."""
    from app.models.learning_history import LearningHistory
    from app.services.asgf_cost_service import ASGF_FREE_TIER_LIMIT

    for i in range(ASGF_FREE_TIER_LIMIT):
        db_session.add(
            LearningHistory(
                student_id=student.id,
                session_id=uuid4().hex,
                session_type="asgf",
                question_asked=f"Q{i}",
            )
        )
    db_session.commit()

    headers = _auth(client, student_user.email)
    resp = client.post(
        "/api/asgf/session",
        json={"question": "What is gravity?"},
        headers=headers,
    )
    assert resp.status_code == 429
    assert "limit reached" in resp.json()["detail"].lower()


def test_create_session_allowed_under_cap(client, db_session, student_user, student):
    """POST /api/asgf/session proceeds when under the cap (mocked AI calls)."""
    headers = _auth(client, student_user.email)

    mock_context = AsyncMock()
    mock_context.return_value = type("Ctx", (), {
        "subject": "Science",
        "grade_level": "9",
        "topic": "Gravity",
        "model_dump": lambda self: {},
    })()

    mock_plan = AsyncMock()
    mock_plan.return_value = type("Plan", (), {
        "topic_classification": {"subject": "Science", "grade_level": "9"},
        "slide_plan": [{"title": "t", "brief": "b", "bloom_tier": "understand"}],
        "quiz_plan": [],
        "estimated_session_time_min": 10,
        "model_dump": lambda self: {},
    })()

    with (
        patch("app.api.routes.asgf.asgf_service.assemble_context_package", mock_context),
        patch("app.api.routes.asgf.asgf_service.generate_learning_cycle_plan", mock_plan),
    ):
        resp = client.post(
            "/api/asgf/session",
            json={"question": "What is gravity?"},
            headers=headers,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
