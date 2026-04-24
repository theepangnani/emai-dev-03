"""Streaming happy-path tests for POST /api/tutor/chat/stream (#4063).

Split from the original ``test_tutor_routes.py`` (#4087 S-7).

Covers
------
- test_stream_happy_path_emits_sse_events — tokens, chips, done events
- test_stream_conversation_id_round_trips — conversation_id reuse
- test_stream_uses_fresh_sessionlocal_for_persistence — #4079 regression
- test_load_history_skips_unpaired_assistant_rows — history walker pairing
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import PASSWORD, _auth
from tutor_helpers import make_user, mock_openai_client, set_tutor_flag


@pytest.fixture(autouse=True)
def _force_openai_key():
    """See tests/test_tutor_routes_auth.py for rationale."""
    with patch("app.api.routes.tutor.settings.openai_api_key", "sk-test-dummy"), patch(
        "app.services.safety_service.settings.openai_api_key", "sk-test-dummy"
    ):
        yield


def test_stream_happy_path_emits_sse_events(client, db_session):
    """Flag-on + mocked OpenAI streams token/chips/done SSE frames."""
    make_user(db_session, email="tutor_happy@test.com")
    set_tutor_flag(db_session, enabled=True)

    mock_client = mock_openai_client(
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
        set_tutor_flag(db_session, enabled=False)


def test_stream_conversation_id_round_trips(client, db_session):
    """A request with conversation_id reuses the same conversation row."""
    make_user(db_session, email="tutor_cid@test.com")
    set_tutor_flag(db_session, enabled=True)

    mock_client = mock_openai_client(stream_pieces=["ok"])
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
        set_tutor_flag(db_session, enabled=False)


def test_stream_uses_fresh_sessionlocal_for_persistence(client, db_session):
    """Persistence in the generator must use a fresh SessionLocal that is
    opened and closed inside the generator — protects against silent write
    loss if the request-scoped session closes before streaming completes
    (#4079).
    """
    from app.db import database as _database_mod

    make_user(db_session, email="tutor_sl@test.com")
    set_tutor_flag(db_session, enabled=True)

    real_sessionlocal = _database_mod.SessionLocal
    created_sessions: list = []

    def _tracking_factory(*args, **kwargs):
        session = real_sessionlocal(*args, **kwargs)
        created_sessions.append(session)
        return session

    mock_client = mock_openai_client(stream_pieces=["Hello"])
    try:
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=mock_client
        ), patch(
            "app.api.routes.tutor.SessionLocal", side_effect=_tracking_factory
        ) as session_local_spy:
            headers = _auth(client, "tutor_sl@test.com")
            resp = client.post(
                "/api/tutor/chat/stream",
                json={"message": "Hi"},
                headers=headers,
            )
            assert resp.status_code == 200
            # Consume the stream so the generator runs to completion.
            _ = resp.text

            # The generator opened its own SessionLocal at least once and
            # the created session(s) are no longer active (closed in finally).
            assert session_local_spy.call_count >= 1
            assert created_sessions, "generator did not open a SessionLocal"
            for s in created_sessions:
                # A closed SQLAlchemy session's `is_active` becomes False
                # after .close() in the common dev (SQLite) configuration.
                assert not s.in_transaction()
    finally:
        set_tutor_flag(db_session, enabled=False)


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

def test_stream_unknown_conversation_id_returns_404(client, db_session):
    """An unknown conversation_id must NOT silently start a new conversation.

    Previously the route would look up the row, fail to find it, leave
    `conversation = None`, and then create a brand-new conversation in the
    generator — masking client bugs and yielding a surprising mismatch
    between the supplied id and the id echoed in the `done` frame.
    """
    from app.models.tutor import TutorConversation

    make_user(db_session, email="tutor_unknown_cid@test.com")
    set_tutor_flag(db_session, enabled=True)

    mock_client = mock_openai_client(stream_pieces=["ok"])
    try:
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=mock_client
        ):
            headers = _auth(client, "tutor_unknown_cid@test.com")
            resp = client.post(
                "/api/tutor/chat/stream",
                json={
                    "message": "hi",
                    "conversation_id": "does-not-exist-xyz",
                },
                headers=headers,
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "conversation_not_found"
        # And no conversation row was created.
        convs = (
            db_session.query(TutorConversation)
            .filter(TutorConversation.id == "does-not-exist-xyz")
            .count()
        )
        assert convs == 0
    finally:
        set_tutor_flag(db_session, enabled=False)


def test_stream_cross_user_conversation_id_returns_404(client, db_session):
    """A conversation_id owned by a DIFFERENT user must return 404 (not leak).

    The row exists — but for someone else. The endpoint must treat it as
    not-found from the caller's perspective rather than letting the second
    user inject messages into another user's conversation.
    """
    from app.models.tutor import TutorConversation

    owner = make_user(db_session, email="tutor_cid_owner@test.com")
    make_user(db_session, email="tutor_cid_other@test.com")
    set_tutor_flag(db_session, enabled=True)

    # Seed a conversation owned by `owner`.
    owned = TutorConversation(id="owned-by-alice", user_id=owner.id)
    db_session.add(owned)
    db_session.commit()

    mock_client = mock_openai_client(stream_pieces=["ok"])
    try:
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=mock_client
        ):
            headers = _auth(client, "tutor_cid_other@test.com")
            resp = client.post(
                "/api/tutor/chat/stream",
                json={
                    "message": "hi",
                    "conversation_id": "owned-by-alice",
                },
                headers=headers,
            )

        assert resp.status_code == 404
        assert resp.json()["detail"] == "conversation_not_found"
    finally:
        set_tutor_flag(db_session, enabled=False)


def test_stream_inter_token_stall_emits_error_frame(client, db_session):
    """A mid-stream hang (no token within INTER_TOKEN_TIMEOUT) emits an
    SSE `error` frame rather than blocking the connection forever."""
    import asyncio as _asyncio

    make_user(db_session, email="tutor_stall@test.com")
    set_tutor_flag(db_session, enabled=True)

    # An async stream whose `__anext__` never resolves — we patch
    # asyncio.wait_for to raise TimeoutError immediately instead of
    # actually waiting 15 seconds.
    class _HangingStream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            # Simulate a stall; wait_for will fire TimeoutError via the patch.
            await _asyncio.sleep(60)

    async def _create(*args, **kwargs):
        return _HangingStream()

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=_create)
    mod_result = MagicMock()
    mod_result.flagged = False
    mod_result.categories.model_dump.return_value = {"hate": False}
    mod_response = MagicMock()
    mod_response.results = [mod_result]
    mock_client.moderations.create = AsyncMock(return_value=mod_response)

    # Patch asyncio.wait_for inside the tutor module so the stall trips
    # immediately without making the test actually wait 15s.
    async def _instant_timeout(awaitable, timeout):
        # Cancel the pending awaitable and raise as real wait_for would.
        try:
            if hasattr(awaitable, "close"):
                awaitable.close()
        except Exception:
            pass
        raise _asyncio.TimeoutError()

    try:
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=mock_client
        ), patch(
            "app.api.routes.tutor.asyncio.wait_for", side_effect=_instant_timeout
        ):
            headers = _auth(client, "tutor_stall@test.com")
            resp = client.post(
                "/api/tutor/chat/stream",
                json={"message": "please stall"},
                headers=headers,
            )

        assert resp.status_code == 200
        body = resp.text
        assert '"type": "error"' in body
        assert '"code": "timeout"' in body
        # No tokens ever emitted.
        assert '"type": "token"' not in body
    finally:
        set_tutor_flag(db_session, enabled=False)


def test_load_history_stable_order_on_timestamp_tie(db_session):
    """Two rows with identical created_at must pair deterministically.

    Without a tiebreak on `id`, SQLite's natural order is implementation-
    defined and the (user, assistant) pairing flips across calls. The
    route adds `.order_by(desc(created_at), desc(id))` to guarantee
    stable pairing.
    """
    from datetime import datetime, timezone

    from app.api.routes.tutor import _load_history
    from app.core.security import get_password_hash
    from app.models.tutor import TutorConversation, TutorMessage
    from app.models.user import User, UserRole

    user = User(
        email="tutor_tiebreak@test.com",
        full_name="Tiebreak",
        role=UserRole.STUDENT,
        hashed_password=get_password_hash(PASSWORD),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    conv = TutorConversation(id="conv-tiebreak", user_id=user.id)
    db_session.add(conv)
    db_session.commit()

    # Two rows with IDENTICAL created_at — realistic under bulk inserts.
    same_ts = datetime(2026, 2, 2, 12, 0, 0, tzinfo=timezone.utc)
    db_session.add(
        TutorMessage(
            id="msg-a-user",
            conversation_id=conv.id,
            role="user",
            content="q_same_ts",
            created_at=same_ts,
        )
    )
    db_session.add(
        TutorMessage(
            id="msg-b-assistant",
            conversation_id=conv.id,
            role="assistant",
            content="a_same_ts",
            created_at=same_ts,
        )
    )
    db_session.commit()

    # Calling twice must return the SAME result (stable order).
    h1 = _load_history(db_session, conv.id)
    h2 = _load_history(db_session, conv.id)
    assert h1 == h2
