"""DCI orchestration service (#4139, M0-4).

Glue between the `POST /api/dci/checkin` endpoint and the rest of the
DCI pipeline:

* `store_artifact_locally`  — file-system stub for GCS object writes
  (TODO M0-fast-follow: swap to ``gs://classbridge-dci/...`` in
  ``northamerica-northeast1`` per § 9 of the design doc).
* `make_signed_url` / `verify_signed_url` — HMAC-tokenised local URL
  scheme that mimics family-scoped signed-URL semantics (TTL ≤ 5 min).
* `run_async_pipeline`      — fan-out background task that calls the
  voice transcription (M0-5) and summary generation (M0-6) services.
  Both are stubbed if not yet on disk.

The service intentionally does **not** import the M0-2 SQLAlchemy
models (``daily_checkins`` / ``classification_events``) directly — the
router persists rows when the models are available, and we keep the
service callable in isolation so unit tests can mock the DB layer.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ── Constants ──────────────────────────────────────────────────────────

# TODO(CB-DCI-001 M0-fast-follow): swap to GCS bucket
#   gs://classbridge-dci/<kid_id>/<yyyy>/<mm>/<dd>/<uuid>
#   under project=emai-dev-01, region=northamerica-northeast1.
DCI_LOCAL_STORAGE_ROOT = Path("app/storage/dci")

PHOTO_MAX_BYTES = 500 * 1024            # 500 KB
VOICE_MAX_BYTES = 5 * 1024 * 1024       # 5 MB (≈ 60 s of 16 kHz mono opus)
TEXT_MAX_CHARS = 280

SIGNED_URL_TTL_SECONDS = 5 * 60         # 5 min — design § 9 / § 11

# ── File-system storage stub ───────────────────────────────────────────


@dataclass
class StoredArtifact:
    """Result of writing a single artifact to local disk."""

    artifact_type: str   # 'photo' | 'voice'
    uri: str             # e.g. 'app/storage/dci/12/2026/04/25/<uuid>.jpg'
    size_bytes: int


def _ext_for(content_type: Optional[str], default: str) -> str:
    """Best-effort extension from a multipart Content-Type."""
    if not content_type:
        return default
    ct = content_type.lower().split(";")[0].strip()
    mapping = {
        "image/jpeg": "jpg",
        "image/jpg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/heic": "heic",
        "audio/webm": "webm",
        "audio/ogg": "ogg",
        "audio/mp4": "m4a",
        "audio/mpeg": "mp3",
        "audio/wav": "wav",
    }
    return mapping.get(ct, default)


def store_artifact_locally(
    *,
    kid_id: int,
    artifact_type: str,
    content: bytes,
    content_type: Optional[str],
) -> StoredArtifact:
    """Persist a photo or voice artifact under a per-kid date-partitioned dir.

    The path mirrors the eventual GCS object key so the cut-over is a
    one-line swap. The dir is created if missing — tests run against
    an isolated tmp DB so this is acceptable.
    """
    if artifact_type not in {"photo", "voice"}:
        raise ValueError(f"unsupported artifact_type: {artifact_type!r}")

    now = datetime.now(timezone.utc)
    default_ext = "jpg" if artifact_type == "photo" else "webm"
    ext = _ext_for(content_type, default_ext)

    dir_path = (
        DCI_LOCAL_STORAGE_ROOT
        / str(kid_id)
        / f"{now:%Y}"
        / f"{now:%m}"
        / f"{now:%d}"
    )
    dir_path.mkdir(parents=True, exist_ok=True)

    file_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = dir_path / file_name
    file_path.write_bytes(content)

    return StoredArtifact(
        artifact_type=artifact_type,
        uri=str(file_path).replace("\\", "/"),
        size_bytes=len(content),
    )


# ── Signed-URL stub (HMAC over uri + expiry) ──────────────────────────


def _signing_key() -> bytes:
    """Use the existing JWT secret as the URL-signing key (M0 only).

    TODO(CB-DCI-001 M0-fast-follow): rotate to a dedicated
    ``DCI_URL_SIGNING_KEY`` env var once GCS signed URLs replace this stub.
    """
    return (settings.secret_key or "dci-dev-key").encode("utf-8")


def make_signed_url(uri: str, *, ttl_seconds: int = SIGNED_URL_TTL_SECONDS) -> str:
    """Return a tokenised URL for a stored artifact.

    Format: ``<uri>?exp=<unix>&sig=<hex>``. Family scoping is enforced
    by the route layer (kid + parent ownership check) before this is
    ever called — the token only proves "the server signed this".
    """
    expiry = int(time.time()) + max(1, ttl_seconds)
    payload = f"{uri}|{expiry}".encode("utf-8")
    sig = hmac.new(_signing_key(), payload, hashlib.sha256).hexdigest()
    return f"{uri}?exp={expiry}&sig={sig}"


def verify_signed_url(uri: str, exp: int, sig: str) -> bool:
    """Constant-time verification of a signed URL token."""
    if int(exp) < int(time.time()):
        return False
    payload = f"{uri}|{int(exp)}".encode("utf-8")
    expected = hmac.new(_signing_key(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


# ── Async fan-out (M0-5 + M0-6 stubs) ─────────────────────────────────


async def _maybe_transcribe_voice(voice_uri: Optional[str]) -> dict:
    """Call ``dci_voice_service.transcribe`` if it exists, else return a stub."""
    if not voice_uri:
        return {"transcript": "", "sentiment_score": 0.0}

    try:
        from app.services import dci_voice_service  # type: ignore
    except ImportError:
        # TODO(CB-DCI-001 M0-5): wire to real Whisper + Haiku sentiment service.
        logger.info(
            "DCI: dci_voice_service not yet implemented (M0-5) — returning stub"
        )
        return {"transcript": "...", "sentiment_score": 0.0}

    try:
        return await dci_voice_service.transcribe(voice_uri)  # type: ignore[attr-defined]
    except Exception:
        logger.exception("DCI voice transcribe failed for %s", voice_uri)
        return {"transcript": "", "sentiment_score": 0.0}


async def _maybe_generate_summary(checkin_id: int, kid_id: int) -> Optional[dict]:
    """Call ``dci_summary_service.generate`` if it exists, else return a stub."""
    try:
        from app.services import dci_summary_service  # type: ignore
    except ImportError:
        # TODO(CB-DCI-001 M0-6): wire to Sonnet 4.6 + prompt-cache summary service.
        logger.info(
            "DCI: dci_summary_service not yet implemented (M0-6) — returning stub"
        )
        return None

    try:
        return await dci_summary_service.generate(  # type: ignore[attr-defined]
            checkin_id=checkin_id, kid_id=kid_id,
        )
    except Exception:
        logger.exception(
            "DCI summary generate failed for checkin_id=%s kid_id=%s",
            checkin_id,
            kid_id,
        )
        return None


async def run_async_pipeline(
    *,
    checkin_id: int,
    kid_id: int,
    voice_uri: Optional[str],
) -> dict:
    """Background task: voice transcribe + summary generate (M0-5 + M0-6 stubs).

    Kept side-effect-light for M0 — real implementations land in the
    M0-5 and M0-6 stripes. This function never raises so background
    failures don't crash the worker.

    Caller contract: ``checkin_id`` MUST reference a real
    ``daily_checkins.id``. The route layer skips the schedule call
    when persistence was a no-op so this function never sees a
    placeholder ID. (PR-review pass 2 [P2-I1].)
    """
    voice_result = await _maybe_transcribe_voice(voice_uri)
    summary_result = await _maybe_generate_summary(checkin_id, kid_id)

    logger.info(
        "DCI async pipeline completed: checkin_id=%s voice=%s summary=%s",
        checkin_id,
        bool(voice_result.get("transcript")),
        summary_result is not None,
    )
    return {
        "voice": voice_result,
        "summary": summary_result,
    }


# ── Status snapshot helper ────────────────────────────────────────────


def status_snapshot(checkin_id: int) -> dict:
    """Return a minimal processing-state payload for the polling endpoint.

    M0 implementation is intentionally a stub: until the daily_checkins
    + classification_events tables (M0-2) and the summary writer (M0-6)
    are in place, we cannot reflect real DB state. The endpoint shape is
    fixed so the kid web flow (M0-9) can be wired against it now.
    """
    return {
        "checkin_id": checkin_id,
        "state": "pending",
        "voice_transcribed": False,
        "summary_ready": False,
        # TODO(CB-DCI-001 M0-2 + M0-6): join daily_checkins,
        # classification_events, ai_summaries to populate real state.
    }
