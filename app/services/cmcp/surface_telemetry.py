"""CB-CMCP-001 M3α 3C-5 — Surface integration telemetry helpers (#4581).

Structured-log telemetry for the 3 surface integration paths the M3α
batch ships (Bridge, DCI, Digest). Three log shapes — one per stage of
the surface lifecycle — so the M3 acceptance gate (24h-surface rate,
render rate, CTR per surface) is measurable from the standard log feed
without requiring a separate metrics pipeline.

Stripe scope (per #4581 + plan §7 M3-C 3C-5)
--------------------------------------------
- Pure-logic helpers: :func:`log_dispatched`, :func:`log_rendered`,
  :func:`log_ctr`. Each emits exactly one structured INFO log line
  matching the existing :mod:`app.services.cmcp.generation_telemetry`
  shape (human-readable message + ``extra=`` dict for log-based metric
  extraction).
- Helpers are invoked by sibling stripes:
  * 3C-1 (Wave 2 surface dispatcher) calls :func:`log_dispatched` after
    fan-out completes.
  * 3C-2 (DCI block render) + 3C-3 (digest block render) call
    :func:`log_rendered` when an artifact actually renders for a user.
  * The new ``GET /api/cmcp/surfaces/{surface}/click`` endpoint in
    ``app/api/routes/cmcp_surface_click.py`` calls :func:`log_ctr` and
    302-redirects to the canonical artifact view.

Out of scope
------------
- Aggregation / dashboard / metrics pipeline — M3-H (β).
- Per-surface dashboards or alert rules — operations concern.

Trust boundary
--------------
``surface`` is constrained to the three known paths via
:data:`SURFACES`. Callers that pass an unknown surface get the value
emitted verbatim in the log line — telemetry must never fail closed
and break the surface render path. The ``surface`` value is also
length-checked at the API boundary (the click endpoint validates with
the literal allow-list) so the value reaching log aggregation is
always one of the three expected strings except in caller-bug cases.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Final

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Surface identifiers — single source of truth for the three M3α paths
# ---------------------------------------------------------------------------
#
# Lowercase string literals (matches the URL slug used in the click
# endpoint and the existing surface-dispatcher names in the design doc).
# The set is exported so callers (3C-1, 3C-2, 3C-3, click endpoint) can
# validate against the same allow-list rather than duplicating the
# constant table.
SURFACE_BRIDGE: Final[str] = "bridge"
SURFACE_DCI: Final[str] = "dci"
SURFACE_DIGEST: Final[str] = "digest"

SURFACES: Final[frozenset[str]] = frozenset(
    {SURFACE_BRIDGE, SURFACE_DCI, SURFACE_DIGEST}
)


def _utc_now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 form.

    Used for ``dispatched_at`` / ``rendered_at`` / ``clicked_at`` so the
    log line carries a self-contained timestamp the metric extractor can
    bucket without re-deriving from ``LogRecord.created``.
    """
    return datetime.now(timezone.utc).isoformat()


def log_dispatched(
    artifact_id: int,
    surface: str,
    latency_ms_from_approve: int,
) -> None:
    """Emit a ``cmcp.surface.dispatched`` structured telemetry log line.

    Called by the surface dispatcher (Wave 2 stripe 3C-1) after the
    artifact has been fanned out to the named surface. The 24h-surface
    rate metric is computed from the count of these log lines vs the
    count of approved artifacts in the same window.

    Parameters
    ----------
    artifact_id
        ``study_guides.id`` of the dispatched artifact.
    surface
        One of :data:`SURFACES` (``bridge`` / ``dci`` / ``digest``).
        Unknown values are emitted verbatim — telemetry never raises.
    latency_ms_from_approve
        Wall-clock latency between artifact approval (or creation, for
        SELF_STUDY paths that skip review) and dispatch. Negative values
        are clamped to 0 — defensive against monotonic-clock regressions
        in the dispatcher's timing path.
    """
    if latency_ms_from_approve < 0:
        latency_ms_from_approve = 0

    dispatched_at = _utc_now_iso()
    logger.info(
        "cmcp.surface.dispatched artifact_id=%s surface=%s "
        "latency_ms_from_approve=%d dispatched_at=%s",
        artifact_id,
        surface,
        latency_ms_from_approve,
        dispatched_at,
        extra={
            "event": "cmcp.surface.dispatched",
            "artifact_id": artifact_id,
            "surface": surface,
            "latency_ms_from_approve": latency_ms_from_approve,
            "dispatched_at": dispatched_at,
        },
    )


def log_rendered(
    artifact_id: int,
    surface: str,
    user_id: int,
) -> None:
    """Emit a ``cmcp.surface.rendered`` structured telemetry log line.

    Called from the DCI block render path (3C-2) and the digest block
    render path (3C-3) when an artifact actually paints for a user. The
    render-rate metric is computed from the count of these log lines vs
    the count of dispatched lines in the same window — captures the
    "dispatched but never seen" gap (logged-out users, expired blocks,
    surface-render failures).

    Parameters
    ----------
    artifact_id
        ``study_guides.id`` of the rendered artifact.
    surface
        One of :data:`SURFACES`. Bridge currently does NOT emit a render
        line (the My Hub list view is the artifact list; click
        navigation is the next signal). DCI + digest are the two surfaces
        with a passive-render telemetry need.
    user_id
        ``users.id`` of the viewer. Required so per-user uniqueness can
        be re-derived downstream — multiple renders of the same artifact
        to the same user are still recorded (we don't dedupe in-process)
        but the metric extractor can collapse if needed.
    """
    rendered_at = _utc_now_iso()
    logger.info(
        "cmcp.surface.rendered artifact_id=%s surface=%s user_id=%s "
        "rendered_at=%s",
        artifact_id,
        surface,
        user_id,
        rendered_at,
        extra={
            "event": "cmcp.surface.rendered",
            "artifact_id": artifact_id,
            "surface": surface,
            "user_id": user_id,
            "rendered_at": rendered_at,
        },
    )


def log_ctr(
    artifact_id: int,
    surface: str,
    user_id: int,
) -> None:
    """Emit a ``cmcp.surface.ctr`` structured telemetry log line.

    Called from the click-redirect endpoint when a user clicks an
    "Open in Bridge" link (or equivalent surface-specific CTA). The
    CTR-per-surface metric is computed from the count of these log
    lines vs the count of rendered lines (or dispatched lines for
    Bridge, which has no passive-render signal) in the same window.

    Parameters
    ----------
    artifact_id
        ``study_guides.id`` of the clicked artifact.
    surface
        One of :data:`SURFACES`.
    user_id
        ``users.id`` of the clicker. Required for the CTR funnel join
        with the matching ``cmcp.surface.rendered`` line.
    """
    clicked_at = _utc_now_iso()
    logger.info(
        "cmcp.surface.ctr artifact_id=%s surface=%s user_id=%s "
        "clicked_at=%s",
        artifact_id,
        surface,
        user_id,
        clicked_at,
        extra={
            "event": "cmcp.surface.ctr",
            "artifact_id": artifact_id,
            "surface": surface,
            "user_id": user_id,
            "clicked_at": clicked_at,
        },
    )


__all__ = [
    "SURFACE_BRIDGE",
    "SURFACE_DCI",
    "SURFACE_DIGEST",
    "SURFACES",
    "log_dispatched",
    "log_rendered",
    "log_ctr",
]
