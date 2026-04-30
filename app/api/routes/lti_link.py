"""CB-CMCP-001 M3β 3E-4 — Minimal LTI 1.3 deep-link stub (#4655).

Board admins paste a ClassBridge artifact URL into their LMS so a
launching kid lands on the artifact. This is **not** a full LTI 1.3
implementation — only the deep-link verification path. Full OIDC
handshake, Names and Roles roster sync, and grade passback are out of
scope (deferred to a later stripe).

Endpoint
--------
``GET /api/lti/launch?artifact_id={id}&signed_token={jwt}``

The JWT signature is verified against the same dev-03 secret used for
internal access tokens (``settings.secret_key`` + ``settings.algorithm``,
HS256 by default). The board's IT team will be issued a shared-secret
copy out-of-band when they wire the integration; rotating that secret
rotates LTI link-outs alongside the rest of the auth surface.

JWT shape (board IT consumers)
------------------------------
This is the contract board IT teams build against::

    Header
    ------
    { "alg": "HS256", "typ": "JWT" }

    Payload
    -------
    {
      "kid_id":      <int>,    # User.id of the kid the artifact is launching for
      "artifact_id": <int>,    # study_guides.id; must equal the query param
      "exp":         <int>,    # UTC unix timestamp; rejected after this moment
      "type":        "lti_launch"   # constant string; helps reject misuse of
                                    # other JWTs (access/refresh) on this surface
    }

    Signature
    ---------
    HMAC-SHA256 over the encoded header + "." + encoded payload using the
    shared secret. Boards should treat the secret like any other API
    credential — store in their LMS secret manager, rotate on cadence.

Validation order (mirrors M3α visibility helpers)
-------------------------------------------------
1. JWT signature + structure: invalid → 401.
2. Expiry: ``exp < now`` → 401.
3. ``type`` claim must equal ``"lti_launch"`` → 401 otherwise. This
   prevents other JWT shapes (access tokens, password-reset tokens) from
   being replayed at the LTI endpoint and inheriting the redirect
   behavior.
4. ``artifact_id`` and ``kid_id`` claims must be present + ints → 401.
5. ``signed_token.artifact_id`` must equal the ``artifact_id`` query
   parameter → 401. This binds the URL to the token; a token issued
   for artifact 7 cannot be replayed against artifact 8.
6. Artifact lookup → 404 if missing.
7. Kid user lookup → 404 if the ``kid_id`` doesn't resolve to a User row.
8. Kid role: the resolved user MUST have the ``STUDENT`` role → 404
   otherwise. This is the "kid_id" name promise to board IT — the
   token can only assert a student identity, not an admin one. Without
   this gate, a board (intentionally or by mistake) issuing a token
   with ``kid_id`` set to an ADMIN/CURRICULUM_ADMIN user id would have
   ``_user_can_view`` short-circuit ``True`` and grant cross-tenant
   access via the role bypass.
9. Visibility: artifact must be visible to the resolved kid user via
   the M3α ``_user_can_view`` helper → 404 otherwise (collapsed with
   unknown-id to avoid the existence oracle on the public LTI surface).

Rate limiting
-------------
30/minute per client IP via slowapi (mirrors auth.py public surfaces:
register/forgot-password 3/min, login 5/min, unsubscribe 5/min). The
endpoint is intentionally auth-free, so we bound HMAC-verification +
DB-touch traffic against probe abuse. 30/min comfortably accommodates
a class of 30 launching the same artifact in one minute.

On success: 302 redirect to ``/parent/companion/{artifact_id}`` —
matches the canonical artifact-view path used by the rest of the M3
surface stripes.

Out of scope
------------
- Full LTI 1.3 OIDC login init / launch flow.
- LTI Names and Roles service (roster sync).
- LTI Assignment and Grade Service (grade passback).
- Per-board key rotation; today's implementation uses the dev-03
  shared secret for all boards. M3-E or later may add a board-keyed
  asymmetric variant.
- Session establishment for the launching user. The redirect lands the
  caller on the in-app frontend route, which will run the existing
  auth flow (login/SSO) before rendering the artifact. The LTI stub
  only proves the link itself is authentic.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lti", tags=["LTI Link-Out"])


# ---------------------------------------------------------------------------
# Constants — public contract for board IT consumers.
# ---------------------------------------------------------------------------

#: ``type`` claim value the link-out endpoint accepts. Documented in the
#: module docstring; constants imported here so tests + future signers
#: reference one source of truth.
LTI_LAUNCH_TOKEN_TYPE = "lti_launch"


def _decode_lti_token(signed_token: str) -> dict[str, Any]:
    """Decode + validate an LTI deep-link JWT.

    Returns the payload dict on success. Raises :class:`HTTPException`
    with status 401 for any signature, structure, type, or expiry
    failure. The error responses are intentionally generic ("Invalid
    LTI token") so a probing caller can't distinguish "bad signature"
    from "expired" from "wrong type" — same posture as the rest of the
    auth surface (see ``decode_password_reset_token``).
    """
    try:
        payload = jwt.decode(
            signed_token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except JWTError:
        # Covers invalid signature, malformed token, AND expired token —
        # ``jose.jwt.decode`` raises ``ExpiredSignatureError`` (a JWTError
        # subclass) when ``exp`` is past, so a single except branch maps
        # both expiry + signature failures to the same generic 401.
        raise HTTPException(
            status_code=401, detail="Invalid LTI token"
        )

    if payload.get("type") != LTI_LAUNCH_TOKEN_TYPE:
        raise HTTPException(
            status_code=401, detail="Invalid LTI token"
        )

    # ``artifact_id`` + ``kid_id`` must be present AND be ints. ``bool``
    # is a subclass of ``int`` in Python, so reject it explicitly to
    # avoid a True/False sneaking through as 1/0 row lookups.
    raw_artifact = payload.get("artifact_id")
    raw_kid = payload.get("kid_id")
    if not isinstance(raw_artifact, int) or isinstance(raw_artifact, bool):
        raise HTTPException(
            status_code=401, detail="Invalid LTI token"
        )
    if not isinstance(raw_kid, int) or isinstance(raw_kid, bool):
        raise HTTPException(
            status_code=401, detail="Invalid LTI token"
        )

    return payload


@router.get(
    "/launch",
    status_code=302,
    response_class=RedirectResponse,
)
@limiter.limit("30/minute")
def lti_launch(
    request: Request,
    artifact_id: int = Query(
        ...,
        description="study_guides.id of the artifact the LMS link points to",
    ),
    signed_token: str = Query(
        ...,
        description="HS256-signed JWT — see module docstring for shape",
    ),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """LTI 1.3 deep-link stub: validate token, redirect to artifact view.

    Returns a 302 to ``/parent/companion/{artifact_id}`` on success.
    Returns 401 for any signature / expiry / type / claim-shape failure
    and 404 for any resolution / visibility failure. See the module
    docstring for the full validation order + JWT contract.

    The endpoint is deliberately auth-free — the JWT signature is the
    authorization proof. Other M3 surface routes use
    ``require_cmcp_enabled`` (which calls ``get_current_user``); LTI
    launches are anonymous from the LMS perspective and pick up the
    user identity inside the redirected frontend route.
    """
    payload = _decode_lti_token(signed_token)

    token_artifact_id = payload["artifact_id"]
    token_kid_id = payload["kid_id"]

    # Bind the URL to the token — a token issued for artifact 7 cannot
    # be replayed against artifact 8 by editing the query string.
    if token_artifact_id != artifact_id:
        raise HTTPException(
            status_code=401, detail="Invalid LTI token"
        )

    # Lazy imports — the conftest model-reload sequence relies on route
    # modules NOT eagerly importing SQLAlchemy mapper classes at module
    # top, so direct `from app.api.routes.lti_link import ...` in tests
    # doesn't pin the pre-reload mapper registry. Mirrors the lazy
    # `_user_can_view` import below.
    from app.models.study_guide import StudyGuide
    from app.models.user import User, UserRole

    artifact = (
        db.query(StudyGuide).filter(StudyGuide.id == artifact_id).first()
    )
    if artifact is None:
        raise HTTPException(
            status_code=404, detail=f"Artifact {artifact_id} not found"
        )

    kid_user = db.query(User).filter(User.id == token_kid_id).first()
    if kid_user is None:
        # Collapsed with unknown-artifact 404 to avoid the existence
        # oracle — a probing caller learns "either the artifact or the
        # kid id is wrong" without which-one-failed signal.
        raise HTTPException(
            status_code=404, detail=f"Artifact {artifact_id} not found"
        )

    # Tighten the ``kid_id`` claim contract: the token must assert a
    # STUDENT identity. Without this gate, a board issuing a token with
    # ``kid_id`` set to an ADMIN / CURRICULUM_ADMIN user id would have
    # ``_user_can_view`` short-circuit ``True`` via the role bypass and
    # grant cross-tenant launch access. This matches the docstring
    # framing ("the kid the artifact is launching for") and the M3-E
    # use case (LMS launches the in-app companion view for a student).
    # Collapsed to the same generic 404 to avoid leaking which check
    # failed.
    if not kid_user.has_role(UserRole.STUDENT):
        raise HTTPException(
            status_code=404, detail=f"Artifact {artifact_id} not found"
        )

    # Lazy import — keeps this route module importable without dragging
    # the MCP tool registry into FastAPI startup before the router list
    # assembles. Mirrors the pattern in ``cmcp_surface_click``.
    from app.mcp.tools.get_artifact import _user_can_view

    if not _user_can_view(artifact, kid_user, db):
        # Collapse access-denied to 404 on the public LTI surface to
        # match ``GET /api/cmcp/surfaces/{surface}/click`` and the
        # parent-companion endpoint convention — don't leak artifact
        # existence to LMS link consumers.
        raise HTTPException(
            status_code=404, detail=f"Artifact {artifact_id} not found"
        )

    logger.info(
        "lti.launch.ok artifact_id=%s kid_id=%s",
        artifact.id,
        token_kid_id,
    )

    # Use ``artifact.id`` (the verified row's id) rather than the query
    # parameter when constructing the redirect target — matches the
    # ``cmcp_surface_click`` convention and avoids reflecting unverified
    # query input into the Location header. Functionally equivalent on
    # the happy path (``token_artifact_id == artifact_id == artifact.id``
    # by this point) but obviously safe at a glance.
    return RedirectResponse(
        url=f"/parent/companion/{artifact.id}", status_code=302
    )


__all__ = ["router", "LTI_LAUNCH_TOKEN_TYPE"]
