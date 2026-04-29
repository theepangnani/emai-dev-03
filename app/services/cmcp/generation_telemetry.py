"""CB-CMCP-001 M1-E 1E-2 — Per-content-type latency telemetry + SLO alerts (#4495).

Emits a structured ``cmcp.generation.latency`` log line on every generation
call (sync 1A-2 + streaming 1E-1) with the per-content-type SLO threshold
applied so dashboards and alert rules can surface SLA breaches without
re-deriving the threshold table at query time.

Per-content-type SLO targets (locked plan §10 risk row + §8.3 telemetry
row + D6=B): see ``_SLO_THRESHOLDS_MS`` below.

Stripe scope (#4495)
--------------------
- Pure-logic emit helper: ``emit_latency_telemetry(content_type,
  latency_ms, request_id)`` resolves the SLO for the given content type,
  computes ``slo_breached`` and emits the structured log line.
- The HTTP-side ``HTTPContentType`` literal (uppercase) is the contract
  for ``content_type`` — matches the schemas in ``app/schemas/cmcp.py``
  and the ``_CONTENT_TYPE_MAP`` keys in 1A-2 / 1E-1.
- Cloud Monitoring custom-metric extraction is infra (deferred to a
  later operations stripe). For this stripe, the structured log line is
  sufficient — the metric extractor can read ``cmcp.generation.latency``
  + ``slo_breached`` off the LogRecord ``extra`` dict directly.

Out of scope
------------
- Aggregation / percentile bucketing — Cloud Monitoring extraction
  handles that downstream.
- Alerting policy wiring — operations concern, not part of this stripe.
- Async / streaming-specific accumulation — both routes call this helper
  exactly once at request-end (after ``done`` for the stream path).

Trust boundary
--------------
``content_type`` and ``request_id`` are caller-supplied. Unknown
content types fall through to ``slo_breached=False`` with a sentinel
``slo_threshold_ms=None`` rather than raising — telemetry must never
fail closed and break the route. The unknown branch is logged at
``WARNING`` so a regression that drops a content-type entry from
``_SLO_THRESHOLDS_MS`` is visible in the log feed.
"""
from __future__ import annotations

import logging
from typing import Final

from app.schemas.cmcp import HTTPContentType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-content-type SLO P95 targets — locked plan §10 + D6=B
# ---------------------------------------------------------------------------
#
# Wall-clock SLA budget from start-of-request through end-of-stream (or
# end-of-sync-response). Values are milliseconds so the comparison stays
# integer-safe for the ``slo_breached`` flag — ``latency_ms`` is also
# integer ms in both routes.
#
# Quiz / Worksheet / Parent Companion are short-form (single-shot) and
# fit well under 12s. Study Guide / Sample Test / Assignment are
# long-form streaming responses; the larger budget reflects realistic
# Claude streaming time for multi-paragraph artifacts.
_SLO_THRESHOLDS_MS: Final[dict[HTTPContentType, int]] = {
    "QUIZ": 8_000,
    "WORKSHEET": 12_000,
    "STUDY_GUIDE": 25_000,
    "SAMPLE_TEST": 40_000,
    "ASSIGNMENT": 30_000,
    "PARENT_COMPANION": 8_000,
}


def get_slo_threshold_ms(content_type: str) -> int | None:
    """Return the SLO P95 threshold (ms) for a content type, or ``None``.

    Public helper so a future operations stripe can build alerting rules
    off the same source of truth as the route-side breach flag — keeps
    the SLO table single-sourced rather than duplicated in YAML.
    """
    return _SLO_THRESHOLDS_MS.get(content_type)  # type: ignore[arg-type]


def emit_latency_telemetry(
    content_type: str,
    latency_ms: int,
    request_id: str,
) -> None:
    """Emit a ``cmcp.generation.latency`` structured telemetry log line.

    Resolves the per-content-type SLO threshold, computes
    ``slo_breached`` (``latency_ms > threshold``), and emits a single
    INFO-level log line with both the human-readable message and the
    structured ``extra=`` payload Cloud Monitoring extraction reads.

    Parameters
    ----------
    content_type
        HTTP-side content-type literal (uppercase). Should be one of the
        ``HTTPContentType`` values; unknown values are logged at WARNING
        and emitted with ``slo_threshold_ms=None`` / ``slo_breached=False``
        so a typo or new artifact type never breaks the route.
    latency_ms
        End-to-end wall-clock latency in integer milliseconds. Negative
        values are clamped to 0 — defensive against monotonic-clock
        regressions in the route timing path.
    request_id
        Opaque correlation ID. The routes generate this once per request
        (uuid4 hex) so log aggregation can join the latency line to the
        upstream envelope-telemetry line for the same request.
    """
    # Defensive normalization — latency must be a non-negative int. The
    # routes use ``time.perf_counter()`` which is monotonic and won't
    # produce negative deltas, but a future caller might pass through
    # arithmetic that underflows; clamp rather than assert so telemetry
    # never crashes the request path.
    if latency_ms < 0:
        latency_ms = 0

    threshold_ms = _SLO_THRESHOLDS_MS.get(content_type)  # type: ignore[arg-type]
    if threshold_ms is None:
        # Unknown content type — emit a WARNING so the unknown branch is
        # discoverable in logs without crashing telemetry.
        logger.warning(
            "cmcp.generation.latency unknown_content_type=%s latency_ms=%d "
            "request_id=%s",
            content_type,
            latency_ms,
            request_id,
            extra={
                "event": "cmcp.generation.latency",
                "cmcp.generation.latency": latency_ms,
                "content_type": content_type,
                "latency_ms": latency_ms,
                "slo_threshold_ms": None,
                "slo_breached": False,
                "request_id": request_id,
            },
        )
        return

    slo_breached = latency_ms > threshold_ms

    # Structured INFO line. Two parallel surfaces:
    # 1. Human-readable message (for grepping in Cloud Logging UI).
    # 2. ``extra=`` payload — Cloud Monitoring's log-based metric
    #    extractor pulls ``cmcp.generation.latency`` + ``slo_breached``
    #    off the LogRecord's structured fields without restringifying.
    logger.info(
        "cmcp.generation.latency content_type=%s latency_ms=%d "
        "slo_threshold_ms=%d slo_breached=%s request_id=%s",
        content_type,
        latency_ms,
        threshold_ms,
        slo_breached,
        request_id,
        extra={
            "event": "cmcp.generation.latency",
            "cmcp.generation.latency": latency_ms,
            "content_type": content_type,
            "latency_ms": latency_ms,
            "slo_threshold_ms": threshold_ms,
            "slo_breached": slo_breached,
            "request_id": request_id,
        },
    )
