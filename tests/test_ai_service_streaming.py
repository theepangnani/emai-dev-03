"""Tests for generate_study_guide_stream() in ai_service.py.

Unit tests for the async generator that streams study guide content
via the Anthropic streaming API.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ── Helper: build a mock Anthropic streaming context manager ─────────


class FakeTextStream:
    """Async iterator that yields text chunks."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._idx]
        self._idx += 1
        return chunk


class FakeStreamContext:
    """Mimics the async context manager returned by client.messages.stream()."""

    def __init__(self, chunks, stop_reason="end_turn", input_tokens=10, output_tokens=50):
        self._chunks = chunks
        self._stop_reason = stop_reason
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    @property
    def text_stream(self):
        return FakeTextStream(self._chunks)

    async def get_final_message(self):
        msg = MagicMock()
        msg.usage.input_tokens = self._input_tokens
        msg.usage.output_tokens = self._output_tokens
        msg.stop_reason = self._stop_reason
        return msg


def _mock_client_with_stream(chunks, stop_reason="end_turn", input_tokens=10, output_tokens=50):
    """Return a mock async Anthropic client whose messages.stream() yields given chunks."""
    client = MagicMock()
    client.messages.stream.return_value = FakeStreamContext(
        chunks, stop_reason=stop_reason,
        input_tokens=input_tokens, output_tokens=output_tokens,
    )
    return client


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestGenerateStudyGuideStream:
    """Unit tests for generate_study_guide_stream()."""

    COMMON_KWARGS = dict(
        assignment_title="Test Assignment",
        assignment_description="Describe photosynthesis.",
        course_name="Biology 101",
    )

    async def test_stream_yields_chunks(self):
        """Verify chunk events are yielded for each text token."""
        from app.services.ai_service import generate_study_guide_stream

        chunks = ["Hello ", "world", "!"]
        mock_client = _mock_client_with_stream(chunks)

        with patch("app.services.ai_service.get_async_anthropic_client", return_value=mock_client):
            events = []
            async for event in generate_study_guide_stream(**self.COMMON_KWARGS):
                events.append(event)

        chunk_events = [e for e in events if e["event"] == "chunk"]
        assert len(chunk_events) == 3
        assert chunk_events[0]["data"] == "Hello "
        assert chunk_events[1]["data"] == "world"
        assert chunk_events[2]["data"] == "!"

    async def test_stream_yields_done_with_full_content(self):
        """Verify done event contains the accumulated full content."""
        from app.services.ai_service import generate_study_guide_stream

        chunks = ["Part A. ", "Part B."]
        mock_client = _mock_client_with_stream(chunks)

        with patch("app.services.ai_service.get_async_anthropic_client", return_value=mock_client):
            events = []
            async for event in generate_study_guide_stream(**self.COMMON_KWARGS):
                events.append(event)

        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        assert done_events[0]["data"]["full_content"] == "Part A. Part B."
        assert done_events[0]["data"]["is_truncated"] is False

    async def test_stream_detects_truncation(self):
        """When stop_reason is 'max_tokens', is_truncated should be True."""
        from app.services.ai_service import generate_study_guide_stream

        chunks = ["Some content"]
        mock_client = _mock_client_with_stream(chunks, stop_reason="max_tokens")

        with patch("app.services.ai_service.get_async_anthropic_client", return_value=mock_client):
            events = []
            async for event in generate_study_guide_stream(**self.COMMON_KWARGS):
                events.append(event)

        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        assert done_events[0]["data"]["is_truncated"] is True

    async def test_stream_handles_api_error(self):
        """When client raises an exception, an error event is yielded."""
        from app.services.ai_service import generate_study_guide_stream
        import anthropic

        mock_client = MagicMock()
        mock_client.messages.stream.side_effect = Exception("Connection failed")

        with patch("app.services.ai_service.get_async_anthropic_client", return_value=mock_client):
            events = []
            async for event in generate_study_guide_stream(**self.COMMON_KWARGS):
                events.append(event)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert "error" in error_events[0]["event"]

    async def test_stream_captures_token_usage(self):
        """After successful stream, _last_ai_usage context var is populated."""
        from app.services.ai_service import generate_study_guide_stream, get_last_ai_usage

        chunks = ["Content"]
        mock_client = _mock_client_with_stream(chunks, input_tokens=100, output_tokens=200)

        with patch("app.services.ai_service.get_async_anthropic_client", return_value=mock_client):
            async for _ in generate_study_guide_stream(**self.COMMON_KWARGS):
                pass

        usage = get_last_ai_usage()
        assert usage is not None
        assert usage["prompt_tokens"] == 100
        assert usage["completion_tokens"] == 200
        assert usage["total_tokens"] == 300
