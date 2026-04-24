"""Shared helpers for test_tutor_routes_* test files (#4087 S-7).

Extracted from the original ``tests/test_tutor_routes.py`` during the
515-line file split. Holds the OpenAI mock builders, feature-flag toggle,
and user factory used across the auth / streaming / moderation test files.
"""
from __future__ import annotations

from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

from conftest import PASSWORD


def set_tutor_flag(db_session, enabled: bool) -> None:
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


def make_user(db_session, *, email: str):
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


def mock_openai_client(
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
