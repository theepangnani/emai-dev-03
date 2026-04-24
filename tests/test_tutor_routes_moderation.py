"""Moderation tests for POST /api/tutor/chat/stream (#4063).

Split from the original ``test_tutor_routes.py`` (#4087 S-7).

Covers
------
- test_stream_moderation_blocked_emits_safety_event — flagged → safety frame
- test_stream_moderation_blocked_does_not_create_orphan_conversation — no
  orphan conversation rows on block
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from conftest import _auth
from tutor_helpers import make_user, mock_openai_client, set_tutor_flag


@pytest.fixture(autouse=True)
def _force_openai_key():
    """See tests/test_tutor_routes_auth.py for rationale."""
    with patch("app.api.routes.tutor.settings.openai_api_key", "sk-test-dummy"), patch(
        "app.services.safety_service.settings.openai_api_key", "sk-test-dummy"
    ):
        yield


def test_stream_moderation_blocked_emits_safety_event(client, db_session):
    """Flagged content emits a `safety` JSON frame and no token frames."""
    make_user(db_session, email="tutor_mod@test.com")
    set_tutor_flag(db_session, enabled=True)

    mock_client = mock_openai_client(
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
        set_tutor_flag(db_session, enabled=False)


def test_stream_moderation_blocked_does_not_create_orphan_conversation(
    client, db_session
):
    """Moderation-blocked requests must NOT persist a `tutor_conversations` row.

    Previously the route created + committed a conversation BEFORE calling
    moderation, leaving orphaned rows whenever the message was flagged.
    """
    from app.models.tutor import TutorConversation

    make_user(db_session, email="tutor_mod_orphan@test.com")
    set_tutor_flag(db_session, enabled=True)

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

    mock_client = mock_openai_client(
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
        pass

def test_stream_moderation_unavailable_emits_distinct_frame(client, db_session):
    """When the moderation API raises (outage), fail-closed mode emits a
    `moderation_unavailable` SSE frame — distinct from `moderation_blocked`
    so the UI can show a retry message instead of a content-block message.
    (#4084)"""
    import openai as _openai

    make_user(db_session, email="tutor_mod_unavail@test.com")
    set_tutor_flag(db_session, enabled=True)

    # Build a client whose moderations.create raises, but whose chat stream
    # would work if reached. The route must NOT reach the chat stream.
    client_mock = MagicMock()

    async def _raise_mod(*args, **kwargs):
        raise _openai.APITimeoutError(request=None)

    client_mock.moderations.create = AsyncMock(side_effect=_raise_mod)

    async def _create_chat(*args, **kwargs):
        return _FakeAsyncStream(["should-not-appear"])

    client_mock.chat.completions.create = AsyncMock(side_effect=_create_chat)

    try:
        with patch(
            "app.api.routes.tutor.openai.AsyncOpenAI", return_value=client_mock
        ), patch(
            "app.services.safety_service.settings.moderation_fail_mode", "closed"
        ):
            headers = _auth(client, "tutor_mod_unavail@test.com")
            resp = client.post(
                "/api/tutor/chat/stream",
                json={"message": "Explain photosynthesis"},
                headers=headers,
            )

        assert resp.status_code == 200
        body = resp.text
        assert '"type": "safety"' in body
        assert "moderation_unavailable" in body
        # Distinct from the generic blocked frame.
        assert "moderation_blocked" not in body
        # No tokens streamed when moderation is unavailable.
        assert '"type": "token"' not in body
    finally:
        set_tutor_flag(db_session, enabled=False)

