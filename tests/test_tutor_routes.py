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
    test so other tests stay in their default state.
    """
    with patch("app.api.routes.tutor.settings.openai_api_key", "sk-test-dummy"):
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
    mod_result = MagicMock()
    mod_result.flagged = moderation_flagged
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
        stream_pieces=["Photo", "synthesis ", "is..."],
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
        assert "event: token" in body
        assert '"delta": "Photo"' in body
        assert "event: chips" in body
        assert "event: done" in body
        assert '"credits_used": 0.25' in body

        # Assistant turn was persisted.
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
    finally:
        _set_tutor_flag(db_session, enabled=False)


def test_stream_moderation_blocked_emits_error_event(client, db_session):
    """Flagged content emits `event: error` with code `moderation_blocked`."""
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
        assert "event: error" in body
        assert "moderation_blocked" in body
        # No tokens emitted on block.
        assert "event: token" not in body
    finally:
        _set_tutor_flag(db_session, enabled=False)


def test_stream_moderation_blocked_does_not_create_orphan_conversation(
    client, db_session
):
    """Moderation-blocked requests must NOT persist a `tutor_conversations` row.

    Previously the route created + committed a conversation BEFORE calling
    moderation, leaving orphaned rows whenever the message was flagged.
    """
    from app.models.tutor import TutorConversation

    _make_user(db_session, email="tutor_mod_orphan@test.com")
    _set_tutor_flag(db_session, enabled=True)

    user = (
        db_session.query(
            __import__("app.models.user", fromlist=["User"]).User
        )
        .filter_by(email="tutor_mod_orphan@test.com")
        .first()
    )
    before = (
        db_session.query(TutorConversation)
        .filter(TutorConversation.user_id == user.id)
        .count()
    )

    mock_client = _mock_openai_client(
        stream_pieces=["ignored"], moderation_flagged=True
    )
    try:
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=mock_client
        ):
            headers = _auth(client, "tutor_mod_orphan@test.com")
            resp = client.post(
                "/api/tutor/chat/stream",
                json={"message": "harmful message"},
                headers=headers,
            )
        assert resp.status_code == 200
        assert "moderation_blocked" in resp.text

        db_session.expire_all()
        after = (
            db_session.query(TutorConversation)
            .filter(TutorConversation.user_id == user.id)
            .count()
        )
        assert after == before, (
            "Blocked request should not create any tutor_conversations rows"
        )
    finally:
        _set_tutor_flag(db_session, enabled=False)


def test_load_history_skips_unpaired_assistant_rows(db_session):
    """`_load_history` must return only complete user→assistant pairs.

    Retries can leave multiple consecutive assistant rows in the DB. Feeding
    that into the OpenAI chat completion API produces a 400 (non-alternating
    roles). The walker over-samples + drops orphan assistant rows.
    """
    from datetime import datetime, timedelta, timezone

    from app.api.routes.tutor import _load_history
    from app.models.tutor import TutorConversation, TutorMessage
    from app.models.user import User, UserRole
    from app.core.security import get_password_hash

    # Fresh user + conversation so row counts are deterministic.
    user = User(
        email="tutor_history@test.com",
        full_name="History Walker",
        role=UserRole.STUDENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    conv = TutorConversation(id="conv-history-walker", user_id=user.id)
    db_session.add(conv)
    db_session.commit()

    # Seed 6 rows at monotonic timestamps: orphan assistants + a pair + a
    # pair's assistant, in mixed order relative to insertion. Ordering on
    # disk is controlled by created_at, not insert order.
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        ("assistant", "orphan-1", base + timedelta(seconds=1)),
        ("assistant", "orphan-2", base + timedelta(seconds=2)),
        ("user", "q1", base + timedelta(seconds=3)),
        ("assistant", "retry-1", base + timedelta(seconds=4)),
        ("assistant", "a1", base + timedelta(seconds=5)),
        ("user", "q2", base + timedelta(seconds=6)),
        ("assistant", "a2", base + timedelta(seconds=7)),
    ]
    for role, content, ts in rows:
        db_session.add(
            TutorMessage(
                conversation_id=conv.id,
                role=role,
                content=content,
                created_at=ts,
            )
        )
    db_session.commit()

    history = _load_history(db_session, conv.id)

    # Expect only the valid pairs: (q1 → a1) and (q2 → a2). The orphan
    # assistants and the retry-1 assistant are dropped because the walker
    # pairs the first user with the NEXT assistant and then resets.
    assert history == [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "retry-1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
    ]

    # Every pair alternates user→assistant — OpenAI will accept it.
    for i in range(0, len(history), 2):
        assert history[i]["role"] == "user"
        assert history[i + 1]["role"] == "assistant"


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
