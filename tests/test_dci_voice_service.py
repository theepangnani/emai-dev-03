"""Tests for ``app.services.dci_voice_service`` (CB-DCI-001 M0-5, #4142).

Mocks both the OpenAI Whisper call and the Claude Haiku sentiment call so
the suite never touches the network. Exercises:

* happy path → mocked Whisper + Haiku → structured payload;
* cost-cap exceeded → Whisper NEVER called, fallback payload;
* cache hit → second call returns cached payload without re-mocking;
* transcript_unavailable fallback shape and idempotency.
"""
from __future__ import annotations

import importlib
import io
import wave
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture()
def voice_service(tmp_path, monkeypatch):
    """Reload the service with an isolated, empty cache for every test.

    The module keeps an in-memory ``_memory_cache`` dict — without
    ``importlib.reload`` it would leak across tests in a session and turn
    every assertion into a cache hit. Pointing the disk cache at a
    per-test ``tmp_path`` makes the file-cache assertions hermetic too.
    """
    from app.core import config

    monkeypatch.setattr(
        config.settings, "dci_voice_cache_dir", str(tmp_path / "cache"), raising=True
    )
    monkeypatch.setattr(
        config.settings, "dci_voice_cost_cap_usd", 0.03, raising=True
    )
    monkeypatch.setattr(
        config.settings,
        "dci_voice_whisper_price_per_minute_usd",
        0.006,
        raising=True,
    )
    monkeypatch.setattr(
        config.settings, "dci_voice_cache_ttl_days", 30, raising=True
    )
    # Whisper requires the OpenAI key; populate it so _call_whisper doesn't
    # raise before the patched OpenAI client is hit.
    monkeypatch.setattr(config.settings, "openai_api_key", "test-key", raising=True)

    import app.services.dci_voice_service as svc

    importlib.reload(svc)
    svc._memory_cache.clear()
    return svc


def _make_wav_bytes(seconds: float = 1.0, sample_rate: int = 16_000) -> bytes:
    """Return valid WAV bytes of the requested duration so the wave-header
    parser produces a real number — important for the cost-cap test."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit PCM
        wf.setframerate(sample_rate)
        frame_count = int(seconds * sample_rate)
        wf.writeframes(b"\x00\x00" * frame_count)
    return buf.getvalue()


def _whisper_response(text: str = "I had a good day", language: str = "en", duration: float = 1.0):
    """Mimic the verbose-JSON shape the OpenAI SDK exposes as attributes."""
    return SimpleNamespace(text=text, language=language, duration=duration)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcribe_happy_path(voice_service):
    audio = _make_wav_bytes(seconds=2.0)

    with patch.object(
        voice_service,
        "_call_whisper",
        new=AsyncMock(return_value=("I had a great day at school", "en", 2.0)),
    ) as mock_whisper, patch.object(
        voice_service, "_score_sentiment", new=AsyncMock(return_value=0.75)
    ) as mock_sentiment:
        result = await voice_service.transcribe(audio)

    assert result == {
        "transcript": "I had a great day at school",
        "sentiment_score": 0.75,
        "language": "en",
        "duration_s": 2.0,
        "model_version": "whisper-1+claude-haiku-4-5-20251001",
    }
    mock_whisper.assert_awaited_once()
    mock_sentiment.assert_awaited_once_with("I had a great day at school")


@pytest.mark.asyncio
async def test_transcribe_accepts_filesystem_path(tmp_path, voice_service):
    """Path input should be read off disk and routed through the same flow."""
    wav_path = tmp_path / "kid_clip.wav"
    wav_path.write_bytes(_make_wav_bytes(seconds=1.5))

    with patch.object(
        voice_service,
        "_call_whisper",
        new=AsyncMock(return_value=("Recess was fun", "en", 1.5)),
    ), patch.object(
        voice_service, "_score_sentiment", new=AsyncMock(return_value=0.4)
    ):
        result = await voice_service.transcribe(str(wav_path))

    assert result["transcript"] == "Recess was fun"
    assert result["sentiment_score"] == 0.4
    assert result["duration_s"] == 1.5


# ---------------------------------------------------------------------------
# Cost cap
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cost_cap_exceeded_skips_whisper(voice_service):
    """A 6-minute clip costs ~$0.036 > $0.03 cap → fail closed."""
    audio = _make_wav_bytes(seconds=6 * 60)  # 6 minutes

    with patch.object(
        voice_service, "_call_whisper", new=AsyncMock()
    ) as mock_whisper, patch.object(
        voice_service, "_score_sentiment", new=AsyncMock()
    ) as mock_sentiment:
        result = await voice_service.transcribe(audio)

    # Whisper / Haiku must NOT be invoked once the pre-flight check fails.
    mock_whisper.assert_not_awaited()
    mock_sentiment.assert_not_awaited()

    assert result["transcript_unavailable"] is True
    assert result["reason"] == "cost_exceeded"
    assert result["estimated_cost_usd"] > 0.03
    assert result["duration_s"] == pytest.approx(360.0, rel=0.01)


@pytest.mark.asyncio
async def test_cost_just_under_cap_calls_whisper(voice_service):
    """At 4 minutes (~$0.024) we are under the $0.03 cap and DO transcribe."""
    audio = _make_wav_bytes(seconds=4 * 60)

    with patch.object(
        voice_service,
        "_call_whisper",
        new=AsyncMock(return_value=("kid talking", "en", 240.0)),
    ) as mock_whisper, patch.object(
        voice_service, "_score_sentiment", new=AsyncMock(return_value=0.0)
    ):
        result = await voice_service.transcribe(audio)

    mock_whisper.assert_awaited_once()
    assert "transcript" in result
    assert result.get("transcript_unavailable") is None


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_returns_same_payload_without_recall(voice_service):
    audio = _make_wav_bytes(seconds=1.0)

    with patch.object(
        voice_service,
        "_call_whisper",
        new=AsyncMock(return_value=("hello", "en", 1.0)),
    ) as mock_whisper, patch.object(
        voice_service, "_score_sentiment", new=AsyncMock(return_value=0.1)
    ) as mock_sentiment:
        first = await voice_service.transcribe(audio)
        second = await voice_service.transcribe(audio)

    assert first == second
    # Same input → exactly one Whisper + one Haiku call across two invocations.
    assert mock_whisper.await_count == 1
    assert mock_sentiment.await_count == 1


@pytest.mark.asyncio
async def test_cache_persists_to_disk(tmp_path, voice_service):
    """Disk cache should let a fresh in-memory cache still serve a hit."""
    audio = _make_wav_bytes(seconds=1.0)

    with patch.object(
        voice_service,
        "_call_whisper",
        new=AsyncMock(return_value=("disk cache test", "en", 1.0)),
    ), patch.object(
        voice_service, "_score_sentiment", new=AsyncMock(return_value=0.2)
    ):
        first = await voice_service.transcribe(audio)

    # Wipe the in-memory layer to force a disk read.
    voice_service._memory_cache.clear()

    with patch.object(
        voice_service, "_call_whisper", new=AsyncMock()
    ) as mock_whisper, patch.object(
        voice_service, "_score_sentiment", new=AsyncMock()
    ) as mock_sentiment:
        second = await voice_service.transcribe(audio)

    assert first == second
    mock_whisper.assert_not_awaited()
    mock_sentiment.assert_not_awaited()


# ---------------------------------------------------------------------------
# Transcript-unavailable / idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcript_unavailable_is_idempotent(voice_service):
    """Re-submitting an oversized clip returns the same fallback payload from cache."""
    audio = _make_wav_bytes(seconds=10 * 60)  # 10 minutes — well over cap

    with patch.object(
        voice_service, "_call_whisper", new=AsyncMock()
    ) as mock_whisper:
        first = await voice_service.transcribe(audio)
        second = await voice_service.transcribe(audio)

    assert first == second
    assert first["transcript_unavailable"] is True
    assert first["reason"] == "cost_exceeded"
    mock_whisper.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_input_type_raises(voice_service):
    with pytest.raises(TypeError):
        await voice_service.transcribe(12345)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Sentiment scoring (lightweight unit, no real Anthropic call)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_score_sentiment_clamps_out_of_range(voice_service):
    """Defensive clamp: model can occasionally emit values outside [-1, 1]."""
    fake_message = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", input={"score": 1.5})]
    )
    fake_client = SimpleNamespace(
        messages=SimpleNamespace(create=lambda **_: fake_message)
    )
    with patch(
        "app.services.ai_service.get_anthropic_client", return_value=fake_client
    ):
        score = await voice_service._score_sentiment("anything")
    assert score == 1.0


@pytest.mark.asyncio
async def test_score_sentiment_empty_transcript_returns_zero(voice_service):
    score = await voice_service._score_sentiment("")
    assert score == 0.0


@pytest.mark.asyncio
async def test_score_sentiment_swallows_errors(voice_service):
    def boom(**_):
        raise RuntimeError("anthropic down")

    fake_client = SimpleNamespace(messages=SimpleNamespace(create=boom))
    with patch(
        "app.services.ai_service.get_anthropic_client", return_value=fake_client
    ):
        score = await voice_service._score_sentiment("hello")
    assert score == 0.0
