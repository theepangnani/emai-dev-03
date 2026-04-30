"""CB-CMCP-001 M3α 3C-5 — Surface click-redirect endpoint (#4581).

Records a ``cmcp.surface.ctr`` telemetry event and 302-redirects the
caller to the canonical artifact view. Wired from the surface render
paths (3C-2 DCI block + 3C-3 digest block) so an "Open in Bridge"
link both lands the user on the artifact and emits CTR telemetry in a
single round-trip — no client-side analytics call required.

Endpoint
--------
``GET /api/cmcp/surfaces/{surface}/click?artifact_id={id}``

- ``surface`` ∈ {bridge, dci, digest} — validated against
  :data:`app.services.cmcp.surface_telemetry.SURFACES`.
- ``artifact_id`` — integer query parameter.

Response
--------
- 302 ``Location: /parent/companion/{artifact_id}`` on success.
- 401 when the caller is unauthenticated. Auth resolves via
  ``require_cmcp_enabled`` (which calls ``get_current_user`` first)
  *before* the handler body runs, so the surface allow-list and the
  artifact lookup are unreachable to anonymous callers — flag-state
  probing without a valid token is not possible.
- 404 when the artifact doesn't exist OR the caller has no visibility
  (collapsed to avoid the existence oracle, mirrors
  ``GET /api/cmcp/artifacts/{id}/parent-companion``).
- 422 on unknown surface (only reachable post-auth).

Visibility
----------
Mirrors :func:`app.mcp.tools.get_artifact._user_can_view` — creator,
linked parents, course teachers, ADMIN/CURRICULUM_ADMIN, BOARD_ADMIN
with matching board. STUDENT sees own only.

Out of scope
------------
- Per-surface dashboards / aggregation — M3-H (β).
- Surface-specific deep-link variation (e.g. dci-specific anchor).
  The redirect target is the canonical artifact view today; surface
  stripes that need a different deep-link can extend the mapping
  table here.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.routes.curriculum import require_cmcp_enabled
from app.db.database import get_db
from app.models.study_guide import StudyGuide
from app.models.user import User
from app.services.cmcp.surface_telemetry import SURFACES, log_ctr

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cmcp", tags=["CMCP Surface Telemetry"])


def _redirect_target_for(artifact_id: int) -> str:
    """Return the canonical artifact view URL for *artifact_id*.

    Single-source the redirect target so future surface stripes that
    need a different deep-link path (e.g. teacher review queue for
    PENDING_REVIEW state) can branch from one place.
    """
    return f"/parent/companion/{artifact_id}"


@router.get(
    "/surfaces/{surface}/click",
    status_code=302,
    response_class=RedirectResponse,
)
def surface_click_redirect(
    surface: str,
    artifact_id: int = Query(..., description="study_guides.id of the clicked artifact"),
    current_user: User = Depends(require_cmcp_enabled),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Record CTR telemetry + 302-redirect to the canonical artifact view.

    Validates the surface against the allow-list, looks up the artifact,
    enforces visibility (collapsed 404 for unknown id + access deny),
    emits ``cmcp.surface.ctr`` telemetry, then redirects.

    The redirect URL is intentionally an in-app frontend path (not an
    absolute URL) so the same endpoint works in dev, staging, and prod
    without env-specific config.
    """
    if surface not in SURFACES:
        # 422 mirrors FastAPI's own validation-error semantics — the
        # path parameter would have been a Literal[...] but FastAPI
        # path-param Literal validation is awkward when the surface
        # set may grow in M3-H, so we validate explicitly here.
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown surface {surface!r} — must be one of "
                f"{sorted(SURFACES)}"
            ),
        )

    artifact = (
        db.query(StudyGuide).filter(StudyGuide.id == artifact_id).first()
    )
    if artifact is None:
        raise HTTPException(
            status_code=404, detail=f"Artifact {artifact_id} not found"
        )

    # Lazy import to avoid the cmcp_surface_click ↔ mcp.tools circular
    # at module-load time (the visibility helper sits inside the MCP
    # tool package; importing at module top would drag the tool
    # registry into FastAPI startup before the router list assembles).
    from app.mcp.tools.get_artifact import _user_can_view

    if not _user_can_view(artifact, current_user, db):
        # Collapse 403 → 404 to match the parent-companion endpoint
        # convention — don't leak artifact existence to unrelated
        # callers on the public REST surface.
        raise HTTPException(
            status_code=404, detail=f"Artifact {artifact_id} not found"
        )

    # Telemetry FIRST — emitting before the redirect ensures the CTR
    # is recorded even if the client follows the redirect to a
    # 404-rendering frontend route. The helper never raises.
    log_ctr(artifact_id=artifact.id, surface=surface, user_id=current_user.id)

    return RedirectResponse(
        url=_redirect_target_for(artifact.id), status_code=302
    )


__all__ = ["router"]
