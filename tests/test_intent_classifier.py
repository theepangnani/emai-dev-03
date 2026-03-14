"""Tests for the hybrid keyword + embedding intent classifier."""

import math
from unittest.mock import MagicMock, patch

import pytest

from app.services.intent_classifier import classify_intent
from app.services.intent_embedding_service import (
    IntentEmbeddingService,
    INTENT_ANCHORS,
    CONFIDENCE_THRESHOLD,
    _cosine_similarity,
)


# ---------------------------------------------------------------------------
# Keyword path tests (no API key required)
# ---------------------------------------------------------------------------


def test_keyword_search_intents():
    assert classify_intent("find my courses") == "search"
    assert classify_intent("show me my tasks") == "search"
    assert classify_intent("list my study guides") == "search"
    assert classify_intent("where is my assignment") == "search"
    assert classify_intent("my notes") == "search"
    assert classify_intent("my flashcards") == "search"


def test_keyword_action_intents():
    assert classify_intent("upload a file") == "action"
    assert classify_intent("create a new task") == "action"
    assert classify_intent("add a course") == "action"
    assert classify_intent("generate study guide") == "action"


def test_keyword_help_intents():
    assert classify_intent("how do I connect Google Classroom") == "help"
    assert classify_intent("what is ClassBridge") == "help"
    assert classify_intent("explain the dashboard") == "help"
    assert classify_intent("how to create a task") == "help"
    assert classify_intent("how to find my courses") == "help"


def test_greeting_keywords_route_to_help():
    """Greeting/menu words must route to 'help' (regression #1743)."""
    assert classify_intent("hi") == "help"
    assert classify_intent("hello") == "help"
    assert classify_intent("hey") == "help"
    assert classify_intent("help") == "help"
    assert classify_intent("menu") == "help"
    assert classify_intent("start") == "help"
    assert classify_intent("options") == "help"
    # Case-insensitive
    assert classify_intent("Hi") == "help"
    assert classify_intent("HELLO") == "help"
    assert classify_intent("HEY") == "help"
    assert classify_intent("HELP") == "help"
    assert classify_intent("MENU") == "help"


def test_keyword_defaults_to_help_without_api_key():
    """Unknown messages with no API key must default to 'help'."""
    assert classify_intent("") == "help"
    assert classify_intent("some completely ambiguous phrase") == "help"
    assert classify_intent("hello there") == "help"


def test_single_word_no_api_key_routes_to_search():
    """Single bare-word queries with no help keywords route to search (regression #1733)."""
    assert classify_intent("Haashini") == "search"
    assert classify_intent("Thanushan") == "search"
    assert classify_intent("math") == "search"
    assert classify_intent("Noah") == "search"


def test_keyword_defaults_to_help_with_none_api_key():
    """Explicitly passing None still falls back to 'help'."""
    assert classify_intent("randomwords xyz", openai_api_key=None) == "help"


# ---------------------------------------------------------------------------
# Cosine similarity helper
# ---------------------------------------------------------------------------


def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert _cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert _cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector():
    zero = [0.0, 0.0]
    v = [1.0, 0.0]
    assert _cosine_similarity(zero, v) == 0.0


# ---------------------------------------------------------------------------
# IntentEmbeddingService — mocked OpenAI client
# ---------------------------------------------------------------------------


def _make_embedding_response(vectors: list[list[float]]):
    """Build a fake OpenAI embeddings response."""
    response = MagicMock()
    response.data = [MagicMock(embedding=v) for v in vectors]
    return response


def _build_service_with_anchors(anchor_embeddings: dict[str, list[list[float]]]) -> IntentEmbeddingService:
    """Return a pre-initialized IntentEmbeddingService with provided anchor embeddings."""
    svc = IntentEmbeddingService()
    svc._anchor_embeddings = anchor_embeddings
    svc._ready = True
    return svc


def test_classify_above_threshold_returns_intent():
    """When the best intent scores >= CONFIDENCE_THRESHOLD, return it."""
    # Use simple unit vectors so cosine similarity is exact
    search_anchor = [1.0, 0.0, 0.0]
    help_anchor = [0.0, 1.0, 0.0]
    action_anchor = [0.0, 0.0, 1.0]

    svc = _build_service_with_anchors({
        "search": [search_anchor],
        "help": [help_anchor],
        "action": [action_anchor],
    })

    # A message embedding very close to "search" direction
    msg_vec = [0.99, 0.1, 0.0]
    # Normalise manually to ensure similarity > threshold
    mag = math.sqrt(sum(x * x for x in msg_vec))
    msg_vec = [x / mag for x in msg_vec]

    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _make_embedding_response([msg_vec])

    with patch("openai.OpenAI", return_value=mock_client):
        result = svc.classify("Noah", openai_api_key="test-key")

    assert result == "search"


def test_classify_below_threshold_returns_none():
    """When best similarity < CONFIDENCE_THRESHOLD, return None."""
    # All anchors point in orthogonal directions; message is equally similar to all
    svc = _build_service_with_anchors({
        "search": [[1.0, 0.0, 0.0]],
        "help": [[0.0, 1.0, 0.0]],
        "action": [[0.0, 0.0, 1.0]],
    })

    # Message embedding at equal angle to all — avg similarity will be low
    # (1/sqrt(3) ≈ 0.577, but averaged across orthogonal anchors it's ~0.33)
    msg_vec_raw = [1.0, 1.0, 1.0]
    mag = math.sqrt(3)
    msg_vec = [x / mag for x in msg_vec_raw]

    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = _make_embedding_response([msg_vec])

    with patch("openai.OpenAI", return_value=mock_client):
        result = svc.classify("ambiguous query", openai_api_key="test-key")

    # max per-intent score: each intent has one anchor.
    # score for "search" anchor [1,0,0] vs [1/√3, 1/√3, 1/√3] = 1/√3 ≈ 0.577
    # All three intents get max score 0.577 — below CONFIDENCE_THRESHOLD (0.60), so None expected.
    assert result is None


def test_classify_when_not_ready_returns_none():
    """classify() must short-circuit to None when not initialized."""
    svc = IntentEmbeddingService()
    assert svc._ready is False
    result = svc.classify("anything", openai_api_key="test-key")
    assert result is None


def test_classify_openai_error_returns_none():
    """classify() must return None (not raise) when OpenAI call fails."""
    svc = _build_service_with_anchors({"search": [[1.0, 0.0]], "help": [[0.0, 1.0]], "action": [[0.5, 0.5]]})

    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = RuntimeError("API unavailable")

    with patch("openai.OpenAI", return_value=mock_client):
        result = svc.classify("test message", openai_api_key="test-key")

    assert result is None


def test_initialize_openai_error_sets_not_ready():
    """initialize() must not raise and must set _ready=False on error."""
    svc = IntentEmbeddingService()

    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = RuntimeError("network error")

    with patch("openai.OpenAI", return_value=mock_client):
        svc.initialize(openai_api_key="test-key")

    assert svc._ready is False


def test_classify_intent_uses_embedding_fallback():
    """classify_intent() should use embedding service for ambiguous messages when API key provided."""
    svc_mock = MagicMock()
    svc_mock.classify.return_value = "search"

    with patch("app.services.intent_embedding_service.intent_embedding_service", svc_mock):
        result = classify_intent("Noah", openai_api_key="test-key")

    svc_mock.classify.assert_called_once_with("Noah", "test-key")
    assert result == "search"


def test_classify_intent_embedding_fallback_below_threshold_returns_help():
    """When embedding returns None (below threshold), classify_intent should return 'help'."""
    svc_mock = MagicMock()
    svc_mock.classify.return_value = None

    with patch("app.services.intent_embedding_service.intent_embedding_service", svc_mock):
        result = classify_intent("xyzzy quux", openai_api_key="test-key")

    assert result == "help"
