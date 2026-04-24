"""Tests for CB-TUTOR-002 Phase 1 — POST /api/tutor/chat/stream (#4063).

Covers
------
1. test_stream_requires_auth — missing token returns 401
2. test_stream_feature_flag_off_returns_403 — flag default-off gates the endpoint
3. test_stream_happy_path_emits_sse_events — tokens, chips, done events
4. test_stream_moderation_blocked_emits_error_event — moderation fails closed
5. test_stream_rate_limit_exceeded_returns_429 — slowapi 20/hour per user

Notes
-----
- Unique email per test to avoid collisions with the session-scoped DB.
- `tutor_chat_enabled` flag is toggled per-test and reset in teardown —
  do NOT leave it on; other tests rely on the default-off state.
- OpenAI is patched at the module level (`app.api.routes.tutor.openai`).
"""
from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import PASSWORD, _auth


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


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────


def _set_tutor_flag(db_session, enabled: bool) -> None:
    """Force the `tutor_chat_enabled` flag to the requested state."""
    from app.models.feature_flag import FeatureFlag
    from app.services.feature_seed_service import seed_features

    seed_features(db_session)
    flag = (
        db_session.query(FeatureFlag)
        .filter(FeatureFlag.key == "tutor_chat_enabled")
        .first()
    )
    assert flag is not None, "tutor_chat_enabled must be seeded"
    flag.enabled = bool(enabled)
    db_session.commit()


def _make_user(db_session, *, email: str):
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    existing = db_session.query(User).filter(User.email == email).first()
    if existing:
        return existing

    user = User(
        email=email,
        full_name="Tutor Test",
        role=UserRole.STUDENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class _FakeChunk:
    def __init__(self, text: str):
        delta = MagicMock()
        delta.content = text
        choice = MagicMock()
        choice.delta = delta
        self.choices = [choice]


class _FakeAsyncStream:
    def __init__(self, pieces: list[str]):
        self._pieces = pieces

    def __aiter__(self) -> AsyncIterator[_FakeChunk]:
        return self._gen()

    async def _gen(self):
        for p in self._pieces:
            yield _FakeChunk(p)


def _mock_openai_client(
    *, stream_pieces: list[str], moderation_flagged: bool = False
) -> MagicMock:
    """Build a mock for `openai.AsyncOpenAI(...)` with streaming + moderation."""
    client = MagicMock()

    # chat.completions.create — async, returns an async-iterable stream
    async def _create(*args, **kwargs):
        return _FakeAsyncStream(stream_pieces)

    client.chat.completions.create = AsyncMock(side_effect=_create)

    # moderations.create — async, returns a result with `.flagged`
    # The safety_service reads `results[0].categories.model_dump()` so we
    # provide a mock whose categories.model_dump() returns a dict.
    mod_result = MagicMock()
    mod_result.flagged = moderation_flagged
    mod_result.categories.model_dump.return_value = (
        {"hate": True} if moderation_flagged else {"hate": False}
    )
    mod_response = MagicMock()
    mod_response.results = [mod_result]
    client.moderations.create = AsyncMock(return_value=mod_response)

    return client


# ──────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────


def test_stream_requires_auth(client):
    """POST without an Authorization header returns 401."""
    resp = client.post(
        "/api/tutor/chat/stream",
        json={"message": "Explain photosynthesis"},
    )
    assert resp.status_code == 401


def test_stream_feature_flag_off_returns_403(client, db_session):
    """With `tutor_chat_enabled` off, the endpoint returns 403."""
    _make_user(db_session, email="tutor_flagoff@test.com")
    _set_tutor_flag(db_session, enabled=False)

    headers = _auth(client, "tutor_flagoff@test.com")
    resp = client.post(
        "/api/tutor/chat/stream",
        json={"message": "Explain photosynthesis"},
        headers=headers,
    )
    assert resp.status_code == 403


def test_stream_happy_path_emits_sse_events(client, db_session):
    """Flag-on + mocked OpenAI streams token/chips/done SSE frames."""
    _make_user(db_session, email="tutor_happy@test.com")
    _set_tutor_flag(db_session, enabled=True)

    mock_client = _mock_openai_client(
        stream_pieces=[
            "Photo",
            "synthesis ",
            "is...",
            '\n[[CHIPS: "Go deeper", "Quiz me", "Another example"]]',
        ],
    )
    try:
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=mock_client
        ):
            headers = _auth(client, "tutor_happy@test.com")
            resp = client.post(
                "/api/tutor/chat/stream",
                json={"message": "Explain photosynthesis"},
                headers=headers,
            )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        # JSON-envelope SSE: every frame is `data: {...}`
        assert '"type": "token"' in body
        assert '"text": "Photo"' in body
        assert '"type": "chips"' in body
        assert '"suggestions":' in body
        assert "Go deeper" in body
        assert '"type": "done"' in body
        assert '"credits_used": 0.25' in body
        assert '"conversation_id":' in body
        assert '"message_id":' in body
        # No stray event: lines (we're JSON-envelope only now).
        assert "event: token" not in body

        # Assistant turn was persisted — and the [[CHIPS:...]] block was
        # stripped from the stored content.
        from app.models.tutor import TutorConversation

        convs = (
            db_session.query(TutorConversation)
            .order_by(TutorConversation.created_at.desc())
            .all()
        )
        assert len(convs) >= 1
        latest = convs[0]
        roles = [m.role for m in latest.messages]
        assert "user" in roles and "assistant" in roles
        assistant_msg = next(m for m in latest.messages if m.role == "assistant")
        assert "[[CHIPS" not in assistant_msg.content
    finally:
        _set_tutor_flag(db_session, enabled=False)


def test_stream_conversation_id_round_trips(client, db_session):
    """A request with conversation_id reuses the same conversation row."""
    _make_user(db_session, email="tutor_cid@test.com")
    _set_tutor_flag(db_session, enabled=True)

    mock_client = _mock_openai_client(stream_pieces=["ok"])
    try:
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=mock_client
        ):
            headers = _auth(client, "tutor_cid@test.com")
            resp1 = client.post(
                "/api/tutor/chat/stream",
                json={"message": "first"},
                headers=headers,
            )
            assert resp1.status_code == 200
            # Parse conversation_id out of the `done` frame.
            import json as _json

            cid = None
            for line in resp1.text.splitlines():
                if line.startswith("data: "):
                    payload = _json.loads(line[6:])
                    if payload.get("type") == "done":
                        cid = payload.get("conversation_id")
                        break
            assert cid, "expected conversation_id in done frame"

            resp2 = client.post(
                "/api/tutor/chat/stream",
                json={"message": "second", "conversation_id": cid},
                headers=headers,
            )
            assert resp2.status_code == 200
            cid2 = None
            for line in resp2.text.splitlines():
                if line.startswith("data: "):
                    payload = _json.loads(line[6:])
                    if payload.get("type") == "done":
                        cid2 = payload.get("conversation_id")
                        break
            assert cid2 == cid, "second turn must reuse the same conversation"

            # Only one conversation row for this user.
            from app.models.tutor import TutorConversation
            from app.models.user import User as _U

            user = db_session.query(_U).filter(_U.email == "tutor_cid@test.com").first()
            convs = (
                db_session.query(TutorConversation)
                .filter(TutorConversation.user_id == user.id)
                .all()
            )
            assert len(convs) == 1
    finally:
        _set_tutor_flag(db_session, enabled=False)


def test_stream_moderation_blocked_emits_safety_event(client, db_session):
    """Flagged content emits a `safety` JSON frame and no token frames."""
    _make_user(db_session, email="tutor_mod@test.com")
    _set_tutor_flag(db_session, enabled=True)

    mock_client = _mock_openai_client(
        stream_pieces=["ignored"], moderation_flagged=True
    )
    try:
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=mock_client
        ):
            headers = _auth(client, "tutor_mod@test.com")
            resp = client.post(
                "/api/tutor/chat/stream",
                json={"message": "harmful message"},
                headers=headers,
            )

        assert resp.status_code == 200
        body = resp.text
        assert '"type": "safety"' in body
        assert "moderation_blocked" in body
        # No tokens emitted on block.
        assert '"type": "token"' not in body
    finally:
        _set_tutor_flag(db_session, enabled=False)


def test_stream_rate_limit_exceeded_returns_429(client, db_session, app):
    """With the limiter enabled, the 21st request in an hour returns 429."""
    _make_user(db_session, email="tutor_rl@test.com")
    _set_tutor_flag(db_session, enabled=True)

    # Re-enable the limiter for this test only (conftest disables it globally).
    app.state.limiter.enabled = True
    app.state.limiter.reset()
    try:
        mock_client = _mock_openai_client(stream_pieces=["ok"])
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
        _set_tutor_flag(db_session, enabled=False)
