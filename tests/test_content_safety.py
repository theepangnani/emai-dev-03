"""Tests for check_texts_safe helper and quiz/flashcard safety gates (#2445, #2463)."""

import pytest
from unittest.mock import patch

from conftest import PASSWORD, _auth

from app.services.ai_service import check_texts_safe


@patch("app.services.ai_service.check_content_safe", return_value=(True, ""))
def test_all_safe(mock_check):
    safe, reason = check_texts_safe("hello", "world")
    assert safe is True
    assert reason == ""
    assert mock_check.call_count == 2


@patch("app.services.ai_service.check_content_safe")
def test_first_text_unsafe(mock_check):
    mock_check.return_value = (False, "Blocked")
    safe, reason = check_texts_safe("bad content", "good content")
    assert safe is False
    assert reason == "Blocked"
    # Should stop at first failure
    mock_check.assert_called_once_with("bad content")


@patch("app.services.ai_service.check_content_safe", return_value=(True, ""))
def test_none_values_skipped(mock_check):
    safe, reason = check_texts_safe(None, "", "hello")
    assert safe is True
    # Only "hello" should be checked (None and "" are skipped)
    mock_check.assert_called_once_with("hello")


def test_no_args():
    safe, reason = check_texts_safe()
    assert safe is True
    assert reason == ""


# ---------------------------------------------------------------------------
# Integration test: study guide endpoint rejects short content (#2463)
# ---------------------------------------------------------------------------

@pytest.fixture()
def safety_student(db_session):
    """Create a student user for content safety integration tests."""
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = db_session.query(User).filter(User.email == "safety_student@test.com").first()
    if user:
        return user

    hashed = get_password_hash(PASSWORD)
    user = User(
        email="safety_student@test.com",
        full_name="Safety Student",
        role=UserRole.STUDENT,
        hashed_password=hashed,
    )
    db_session.add(user)
    db_session.commit()
    return user


@patch("app.api.routes.study.check_content_safe", return_value=(True, ""))
def test_study_guide_endpoint_rejects_short_content(mock_safe, client, safety_student):
    """POST /api/study/generate with <50 chars content returns 422 (#2463)."""
    headers = _auth(client, "safety_student@test.com")
    resp = client.post(
        "/api/study/generate",
        json={"content": "Too short"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "couldn't read enough text" in resp.json()["detail"]
