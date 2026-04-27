"""Auth + feature-flag gating tests for POST /api/tutor/chat/stream (#4063).

Split from the original ``test_tutor_routes.py`` (#4087 S-7).

Covers
------
- test_stream_requires_auth — missing token returns 401
- test_stream_feature_flag_off_returns_403 — flag default-off gates the endpoint
- test_stream_rate_limit_exceeded_returns_429 — slowapi 20/hour per user
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from conftest import _auth
from tutor_helpers import make_user, mock_openai_client, set_tutor_flag


@pytest.fixture(autouse=True)
def _force_openai_key():
    """Tutor endpoint calls OpenAI moderation + streaming.

    Both call sites short-circuit when `settings.openai_api_key` is empty
    (the default in tests), so we patch the setting to a dummy value so
    our `openai.AsyncOpenAI` mock actually gets invoked. Reset after each
    test so other tests stay in their default state. The safety service
    reads its own `settings` import, so patch it there too.
    """
    with patch("app.api.routes.tutor.settings.openai_api_key", "sk-test-dummy"), patch(
        "app.services.safety_service.settings.openai_api_key", "sk-test-dummy"
    ):
        yield


def test_stream_requires_auth(client):
    """POST without an Authorization header returns 401."""
    resp = client.post(
        "/api/tutor/chat/stream",
        json={"message": "Explain photosynthesis"},
    )
    assert resp.status_code == 401


def test_stream_feature_flag_off_returns_403(client, db_session):
    """With `tutor_chat_enabled` off, the endpoint returns 403."""
    make_user(db_session, email="tutor_flagoff@test.com")
    set_tutor_flag(db_session, enabled=False)

    headers = _auth(client, "tutor_flagoff@test.com")
    resp = client.post(
        "/api/tutor/chat/stream",
        json={"message": "Explain photosynthesis"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_stream_rate_limit_exceeded_returns_429(client, db_session, app):
    """With the limiter enabled, the 21st request in an hour returns 429."""
    make_user(db_session, email="tutor_rl@test.com")
    set_tutor_flag(db_session, enabled=True)

    # Re-enable the limiter for this test only (conftest disables it globally).
    app.state.limiter.enabled = True
    app.state.limiter.reset()
    try:
        mock_client = mock_openai_client(stream_pieces=["ok"])
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=mock_client
        ):
            headers = _auth(client, "tutor_rl@test.com")
            # 20 successful calls
            for _ in range(20):
                resp = client.post(
                    "/api/tutor/chat/stream",
                    json={"message": "Q"},
                    headers=headers,
                )
                assert resp.status_code == 200

            # 21st call trips the limit
            resp = client.post(
                "/api/tutor/chat/stream",
                json={"message": "Q"},
                headers=headers,
            )
            assert resp.status_code == 429
    finally:
        app.state.limiter.enabled = False
        app.state.limiter.reset()
        set_tutor_flag(db_session, enabled=False)

def test_stream_request_accepts_mode_quick(client, db_session):
    """Request body validation accepts ``{"mode": "quick"}`` (#4375)."""
    make_user(db_session, email="tutor_mode_quick@test.com")
    set_tutor_flag(db_session, enabled=True)

    mock_client = mock_openai_client(stream_pieces=["ok"])
    try:
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=mock_client
        ):
            headers = _auth(client, "tutor_mode_quick@test.com")
            resp = client.post(
                "/api/tutor/chat/stream",
                json={"message": "hi", "mode": "quick"},
                headers=headers,
            )
        assert resp.status_code == 200
    finally:
        set_tutor_flag(db_session, enabled=False)


def test_stream_request_accepts_mode_full(client, db_session):
    """Request body validation accepts ``{"mode": "full"}`` (#4375)."""
    make_user(db_session, email="tutor_mode_full@test.com")
    set_tutor_flag(db_session, enabled=True)

    mock_client = mock_openai_client(stream_pieces=["ok"])
    try:
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=mock_client
        ):
            headers = _auth(client, "tutor_mode_full@test.com")
            resp = client.post(
                "/api/tutor/chat/stream",
                json={"message": "hi", "mode": "full"},
                headers=headers,
            )
        assert resp.status_code == 200
    finally:
        set_tutor_flag(db_session, enabled=False)


def test_stream_request_accepts_mode_omitted(client, db_session):
    """Omitting ``mode`` defaults to quick — backwards compatible (#4375)."""
    make_user(db_session, email="tutor_mode_default@test.com")
    set_tutor_flag(db_session, enabled=True)

    mock_client = mock_openai_client(stream_pieces=["ok"])
    try:
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=mock_client
        ):
            headers = _auth(client, "tutor_mode_default@test.com")
            resp = client.post(
                "/api/tutor/chat/stream",
                json={"message": "hi"},
                headers=headers,
            )
        assert resp.status_code == 200
    finally:
        set_tutor_flag(db_session, enabled=False)


def test_stream_request_rejects_invalid_mode(client, db_session):
    """An unknown ``mode`` value must produce a 422 from request validation (#4375)."""
    make_user(db_session, email="tutor_mode_bad@test.com")
    set_tutor_flag(db_session, enabled=True)

    try:
        headers = _auth(client, "tutor_mode_bad@test.com")
        resp = client.post(
            "/api/tutor/chat/stream",
            json={"message": "hi", "mode": "garbage"},
            headers=headers,
        )
        assert resp.status_code == 422
    finally:
        set_tutor_flag(db_session, enabled=False)


def test_stream_flag_off_returns_403_before_rate_limit(client, db_session, app):
    """Flag-off must short-circuit with 403 BEFORE the rate limiter decrements.

    The flag is enforced via a FastAPI `Depends()` that runs before the
    `@limiter.limit` decorator; this test enables the limiter and then
    asserts that repeated flag-off calls all return 403 (not 429), which
    could only happen if the flag check ran first.
    """
    make_user(db_session, email="tutor_flagoff_rl@test.com")
    set_tutor_flag(db_session, enabled=False)

    app.state.limiter.enabled = True
    app.state.limiter.reset()
    try:
        headers = _auth(client, "tutor_flagoff_rl@test.com")
        # Far more than 20 — the limit is 20/hour. If the decorator fired
        # first we'd see 429 before this loop ended. All must be 403.
        for _ in range(25):
            resp = client.post(
                "/api/tutor/chat/stream",
                json={"message": "blocked by flag"},
                headers=headers,
            )
            assert resp.status_code == 403
    finally:
        app.state.limiter.enabled = False
        app.state.limiter.reset()
