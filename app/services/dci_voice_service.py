"""CB-DCI-001 M0-5 — Voice transcription + sentiment scoring.

Wraps OpenAI Whisper (model ``whisper-1``) for kid voice notes captured by
the Daily Check-In Ritual, layers Claude Haiku 4.5 sentiment analysis on the
transcript, and enforces:

* per-voice-note **cost cap** of ``settings.dci_voice_cost_cap_usd`` — when
  the estimated Whisper spend would exceed the cap we **fail closed** and
  return ``transcript_unavailable=True`` *without* calling Whisper, so we
  never burn the budget we are trying to protect;
* SHA-256 **content cache** with a 30-day TTL (configurable) — re-uploading
  the same audio bytes returns the cached transcript + sentiment so the same
  input always produces the same output (idempotent), and retries don't
  re-bill Whisper.

Mirror of the cost-cap + cache pattern documented in the §9 design lock
(see ``docs/design/CB-DCI-001-daily-checkin.md``). Anthropic SDK usage
follows ``parent_digest_ai_service``.

Issue: #4142
Epic: #4135
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import time
import wave
from pathlib import Path
from typing import Union

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

WHISPER_MODEL = "whisper-1"
SENTIMENT_MODEL = "claude-haiku-4-5-20251001"

# Whisper expects 16 kHz mono. When we cannot read the wave header (non-WAV
# container or malformed file) we fall back to this byte-rate so we can still
# enforce the cost cap pre-flight rather than after we have already paid.
_DEFAULT_BYTES_PER_SECOND = 16_000 * 2  # 16 kHz × 2-byte (16-bit) mono PCM

VoiceInput = Union[str, os.PathLike, bytes, bytearray, memoryview]


# ---------------------------------------------------------------------------
# Cache (in-memory primary + disk-backed for cross-process reuse in dev)
# ---------------------------------------------------------------------------

# OrderedDict gives us O(1) LRU semantics: ``move_to_end`` on access and
# ``popitem(last=False)`` to evict the oldest entry when we go over the cap
# (see ``_evict_oldest_if_over_limit``).
from collections import OrderedDict

_memory_cache: "OrderedDict[str, dict]" = OrderedDict()


def _cache_path_for(content_hash: str) -> Path:
    cache_dir = Path(settings.dci_voice_cache_dir)
    return cache_dir / f"{content_hash}.json"


def _evict_oldest_if_over_limit() -> None:
    """Bound both the in-memory cache and the disk cache directory (#4168).

    The in-memory cache is an ``OrderedDict`` so eviction is O(1) on the
    least-recently-inserted/accessed entry. The disk cache is a plain
    directory of ``<hash>.json`` files; we bound it by total file count and
    delete the oldest by mtime when over the cap. Both share the same
    ``settings.dci_voice_cache_max_entries`` cap so behaviour stays simple.
    """
    max_entries = settings.dci_voice_cache_max_entries
    if max_entries <= 0:
        return  # 0 / negative disables the bound (e.g., tests)

    # In-memory bound — pop oldest until we are under the cap.
    while len(_memory_cache) > max_entries:
        _memory_cache.popitem(last=False)

    # Disk bound — best-effort. We tolerate concurrent writers (file may be
    # gone by the time we try to unlink it) and missing dirs (fresh deploy).
    cache_dir = Path(settings.dci_voice_cache_dir)
    if not cache_dir.exists():
        return
    try:
        files = [p for p in cache_dir.glob("*.json") if p.is_file()]
    except OSError as e:
        logger.warning("DCI voice cache disk-bound list failed: %s", e)
        return
    if len(files) <= max_entries:
        return
    # Sort oldest-first by mtime; break ties by name for determinism.
    try:
        files.sort(key=lambda p: (p.stat().st_mtime, p.name))
    except OSError:
        return
    overflow = len(files) - max_entries
    for path in files[:overflow]:
        try:
            path.unlink()
        except OSError:
            continue


def _load_from_cache(content_hash: str) -> dict | None:
    """Return cached transcription dict, or ``None`` on miss / expiry."""
    ttl_seconds = settings.dci_voice_cache_ttl_days * 86_400

    entry = _memory_cache.get(content_hash)
    if entry is not None:
        if time.time() - entry["_cached_at"] <= ttl_seconds:
            # LRU touch — refresh recency so this entry is *not* the next
            # eviction candidate.
            _memory_cache.move_to_end(content_hash)
            return _strip_meta(entry)
        _memory_cache.pop(content_hash, None)

    path = _cache_path_for(content_hash)
    try:
        with path.open("r", encoding="utf-8") as fh:
            entry = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("DCI voice cache read failed for %s: %s", content_hash, e)
        return None

    cached_at = entry.get("_cached_at", 0)
    if time.time() - cached_at > ttl_seconds:
        # Expired — remove file lazily; ignore failures.
        try:
            path.unlink()
        except OSError:
            pass
        return None

    _memory_cache[content_hash] = entry
    _memory_cache.move_to_end(content_hash)
    _evict_oldest_if_over_limit()
    return _strip_meta(entry)


def _save_to_cache(content_hash: str, payload: dict) -> None:
    entry = {**payload, "_cached_at": time.time()}
    _memory_cache[content_hash] = entry
    _memory_cache.move_to_end(content_hash)

    cache_dir = Path(settings.dci_voice_cache_dir)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        with _cache_path_for(content_hash).open("w", encoding="utf-8") as fh:
            json.dump(entry, fh)
    except OSError as e:
        # Disk cache is best-effort; the in-memory cache still serves the
        # current process. Log once per failure but don't propagate.
        logger.warning("DCI voice cache write failed for %s: %s", content_hash, e)

    # Bound both layers AFTER write so we never exceed the cap by more than
    # a single entry between calls.
    _evict_oldest_if_over_limit()


def _strip_meta(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------


def _read_voice_bytes(voice: VoiceInput) -> tuple[bytes, str]:
    """Coerce ``voice`` to ``(bytes, filename)``.

    The filename is sent to Whisper via the multipart upload — its extension
    is the only signal the API uses to pick a decoder, so we propagate the
    original suffix when we have a path and fall back to ``audio.wav``
    (Whisper's best-supported container) for raw byte input.
    """
    if isinstance(voice, (bytes, bytearray, memoryview)):
        return bytes(voice), "audio.wav"
    if isinstance(voice, (str, os.PathLike)):
        path = Path(voice)
        with path.open("rb") as fh:
            return fh.read(), path.name
    raise TypeError(
        "voice_file_path_or_bytes must be a path or bytes-like object, "
        f"got {type(voice).__name__}"
    )


def _estimate_duration_seconds(content: bytes, filename: str) -> float:
    """Best-effort duration estimate, used for the pre-flight cost check.

    For WAV input we read the canonical wave header — exact and free. For
    other containers we fall back to a 16 kHz mono 16-bit PCM byte-rate
    assumption (per PRD §9 — Whisper ingest target). Over-estimating is the
    safe direction because it can only cause us to *block* a long voice
    note; under-estimating could let us over-spend.
    """
    lower_name = filename.lower()
    if lower_name.endswith(".wav"):
        try:
            with wave.open(io.BytesIO(content), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate() or 16_000
                if rate > 0:
                    return frames / float(rate)
        except (wave.Error, EOFError) as e:
            logger.debug("WAV header parse failed for %s: %s", filename, e)

    # Conservative byte-rate fallback. For compressed formats (mp3, m4a,
    # webm, ogg) this over-estimates duration, which is the safe direction.
    if not content:
        return 0.0
    return len(content) / float(_DEFAULT_BYTES_PER_SECOND)


def _estimate_whisper_cost(duration_s: float) -> float:
    """OpenAI lists Whisper-1 at $0.006 per minute (rounded up to the second)."""
    if duration_s <= 0:
        return 0.0
    minutes = duration_s / 60.0
    return minutes * settings.dci_voice_whisper_price_per_minute_usd


# ---------------------------------------------------------------------------
# Whisper call
# ---------------------------------------------------------------------------


async def _call_whisper(
    content: bytes, filename: str
) -> tuple[str, str | None, float | None]:
    """Return ``(transcript, language, duration_from_api)``.

    The OpenAI ``audio.transcriptions.create`` endpoint accepts a file-like
    tuple ``(filename, bytes, mime_type)`` — propagating the filename lets
    the server-side decoder pick the right format. We request the verbose
    JSON format so we can recover the API's own duration measurement (more
    accurate than our pre-flight estimate) for the response payload.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")

    # Imported lazily to keep the optional dep out of the import chain at
    # service-collection time (mirrors ``help_embedding_service``).
    import openai  # type: ignore[import-not-found]

    client = openai.AsyncOpenAI(api_key=settings.openai_api_key.strip())

    response = await client.audio.transcriptions.create(
        model=WHISPER_MODEL,
        file=(filename, content, "application/octet-stream"),
        response_format="verbose_json",
    )

    # The SDK exposes verbose-JSON fields as attributes on the response object.
    transcript = getattr(response, "text", "") or ""
    language = getattr(response, "language", None)
    duration = getattr(response, "duration", None)
    if duration is not None:
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            duration = None
    return transcript, language, duration


# ---------------------------------------------------------------------------
# Sentiment scoring (Claude Haiku 4.5)
# ---------------------------------------------------------------------------

_SENTIMENT_TOOL_SCHEMA = {
    "name": "score_sentiment",
    "description": (
        "Score the emotional sentiment of a kid's spoken check-in about their "
        "school day on a single -1 to +1 scale. -1 = very negative / upset, "
        "0 = neutral / matter-of-fact, +1 = very positive / excited."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "score": {
                "type": "number",
                "minimum": -1,
                "maximum": 1,
                "description": "Sentiment score in [-1, 1].",
            }
        },
        "required": ["score"],
    },
}

_SENTIMENT_SYSTEM_PROMPT = (
    "You are ClassBridge's sentiment scorer for kid daily check-ins. Read "
    "the transcript of a kid talking about their school day and call the "
    "`score_sentiment` tool exactly once with a single number in [-1, 1]. "
    "-1 = very negative (upset, sad, frustrated), 0 = neutral / matter-of-fact, "
    "+1 = very positive (excited, proud, happy). Be conservative — most "
    "matter-of-fact recaps should sit between -0.2 and +0.2."
)


async def _score_sentiment(transcript: str) -> float | None:
    """Single Haiku 4.5 call returning a clamped score in [-1, 1].

    Returns ``None`` on any scoring failure (Anthropic error, missing
    ``tool_use`` block, unparseable score) so the caller can distinguish a
    *genuinely neutral* recap (``0.0``) from an *unscored* one (``None``)
    and surface a ``sentiment_unavailable`` flag in the response payload
    (#4167). Empty / whitespace-only transcripts return ``0.0`` because
    that *is* a meaningful neutral — there is nothing emotional to score.
    """
    if not transcript or not transcript.strip():
        return 0.0

    # Truncate long transcripts so the sentiment call stays cheap. Logged
    # so callers know the score reflects only the first 4 000 chars — a
    # 5-minute kid recap is typically <1 500 chars, so this triggers only
    # for unusually long clips.
    payload_text = transcript[:4000]
    if len(transcript) > 4000:
        logger.info(
            "DCI sentiment truncated transcript %d -> 4000 chars",
            len(transcript),
        )

    try:
        # Local import keeps the Anthropic SDK out of test collection when
        # the caller stubs ``_score_sentiment`` directly.
        from app.services.ai_service import get_anthropic_client

        client = get_anthropic_client()
        message = await asyncio.to_thread(
            client.messages.create,
            model=SENTIMENT_MODEL,
            max_tokens=128,
            system=_SENTIMENT_SYSTEM_PROMPT,
            tools=[_SENTIMENT_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "score_sentiment"},
            messages=[{"role": "user", "content": payload_text}],
        )

        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                raw = block.input.get("score") if isinstance(block.input, dict) else None
                if raw is None:
                    continue
                try:
                    score = float(raw)
                except (TypeError, ValueError):
                    continue
                # Clamp defensively — the schema says [-1, 1] but the model can
                # still emit out-of-range numbers occasionally.
                return max(-1.0, min(1.0, score))
        logger.warning("Sentiment response missing score tool_use block; marking unavailable")
        return None
    except Exception as e:
        logger.warning("Sentiment scoring failed (marking unavailable): %s", e)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def transcribe(voice_file_path_or_bytes: VoiceInput) -> dict:
    """Transcribe a voice note and score its sentiment.

    Args:
        voice_file_path_or_bytes: Either a filesystem path to the voice file
            or the raw audio bytes. WAV files get an exact duration via the
            wave header; other containers get a conservative byte-rate
            estimate for the cost-cap pre-flight check.

    Returns:
        Success::

            {
                "transcript": "...",
                "sentiment_score": 0.42,
                "sentiment_unavailable": False,  # True if Haiku call failed
                "language": "en",
                "duration_s": 12.3,
                "model_version": "whisper-1+claude-haiku-4-5-20251001",
            }

        ``sentiment_unavailable=True`` means the transcript is valid but
        Anthropic refused / errored — downstream UI should render a
        "couldn't score" state instead of showing the fallback ``0.0`` as a
        genuine neutral recap (#4167).

        Cost-cap exceeded (Whisper NEVER called)::

            {
                "transcript_unavailable": True,
                "reason": "cost_exceeded",
                "estimated_cost_usd": 0.045,
                "duration_s": 7.5,
            }

    Idempotency: the SHA-256 of the audio bytes is the cache key. Repeated
    calls with the same content return the cached payload until the TTL
    expires (default 30 days, configurable via
    ``DCI_VOICE_CACHE_TTL_DAYS``).
    """
    content, filename = _read_voice_bytes(voice_file_path_or_bytes)
    content_hash = hashlib.sha256(content).hexdigest()

    cached = _load_from_cache(content_hash)
    if cached is not None:
        logger.info("DCI voice cache hit | hash=%s", content_hash[:12])
        return cached

    estimated_duration = _estimate_duration_seconds(content, filename)
    estimated_cost = _estimate_whisper_cost(estimated_duration)

    if estimated_cost > settings.dci_voice_cost_cap_usd:
        logger.warning(
            "DCI voice cost-cap exceeded — refusing Whisper call | "
            "duration_s=%.2f | est_cost=$%.4f | cap=$%.4f | hash=%s",
            estimated_duration,
            estimated_cost,
            settings.dci_voice_cost_cap_usd,
            content_hash[:12],
        )
        payload = {
            "transcript_unavailable": True,
            "reason": "cost_exceeded",
            "estimated_cost_usd": round(estimated_cost, 6),
            "duration_s": round(estimated_duration, 3),
        }
        # Cache the refusal too — same input → same output. Otherwise a
        # caller retrying the same oversized file would burn the budget on
        # a duplicate cost-cap check (cheap) but we'd also keep recording
        # the warning above on every retry.
        _save_to_cache(content_hash, payload)
        return payload

    start = time.time()
    transcript, language, api_duration = await _call_whisper(content, filename)
    raw_sentiment = await _score_sentiment(transcript)
    elapsed_ms = (time.time() - start) * 1000

    # ``None`` means the Haiku call failed — surface that to callers via
    # ``sentiment_unavailable`` so a neutral icon means "we scored 0" and
    # not "we couldn't score this" (#4167).
    sentiment_unavailable = raw_sentiment is None
    sentiment_score = 0.0 if sentiment_unavailable else raw_sentiment

    duration_s = api_duration if api_duration is not None else estimated_duration

    payload = {
        "transcript": transcript,
        "sentiment_score": sentiment_score,
        "sentiment_unavailable": sentiment_unavailable,
        "language": language or "unknown",
        "duration_s": round(float(duration_s), 3),
        "model_version": f"{WHISPER_MODEL}+{SENTIMENT_MODEL}",
    }

    logger.info(
        "DCI voice transcription complete | duration_s=%.2f | sentiment=%.2f | "
        "sentiment_unavailable=%s | lang=%s | elapsed_ms=%.0f | hash=%s",
        payload["duration_s"],
        sentiment_score,
        sentiment_unavailable,
        payload["language"],
        elapsed_ms,
        content_hash[:12],
    )

    _save_to_cache(content_hash, payload)
    return payload
