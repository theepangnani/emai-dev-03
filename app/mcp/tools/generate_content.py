"""CB-CMCP-001 M2-B 2B-4 (#4555) — ``generate_content`` MCP tool.

Wraps the M1 Curriculum-Mapped Content Pipeline (``GuardrailEngine`` +
``ClassContextResolver`` + ``VoiceRegistry``) for end-user MCP clients
(Claude Desktop, etc.). Supersedes phase-2's un-curricular
``mcp_generate_*`` tools.

⚠️  Synchronous-by-design (M2 + M1 invariant)
---------------------------------------------
The CB-CMCP-001 implementation plan calls 2B-4 an "async submission"
tool — but for now (M2 + M1 invariant: no artifact persistence) it
returns the same synchronous ``GenerationPreview`` shape as
``POST /api/cmcp/generate`` (route 1A-2). This module DOES NOT enqueue
a job and DOES NOT expose a polling endpoint — those land in M3 when
artifact persistence (1A-3) lands and turns previews into real
artifacts the queue can hand back over time.

If a future stripe wires real async submission, the contract change
goes here: keep the tool name + input schema stable, swap the return
type to ``{job_id: str}``, add a sibling ``get_generation_status`` tool.

Role surface (kept narrow for M2)
---------------------------------
``roles=("TEACHER", "ADMIN")`` per the parent registry entry. The
locked design carves out a self-study generation path for PARENT and
STUDENT (D3=C — see CB-CMCP-001 design doc), but landing it here would
require (a) stricter scope clamping per-role and (b) the parent-
companion + student-self-study templates that the M3-B sub-stripes
own. Self-study generation is intentionally deferred to **M3-B** so
this stripe does not creep into a multi-persona contract during M2.
The route-side ``POST /api/cmcp/generate`` already performs the
parent / student persona derivation for the REST surface and is
unchanged by this stripe.

Reuse posture
-------------
The handler imports :func:`app.api.routes.cmcp_generate.generate_cmcp_preview_sync`
— extracted in this stripe for exactly this reason. The MCP surface
and the REST surface share the prompt-construction pipeline byte-for-byte;
duplicating the resolve / build / preview logic across two call-sites
would be a regression (the locked design forbids it — see plan §7
M2-B note "Reuse the route's service layer rather than duplicating
prompt-build logic").

Failure modes (mapped to MCP transport)
---------------------------------------
- ``cmcp.enabled`` OFF → :class:`MCPToolAccessDeniedError` (dispatcher
  → 403). Mirrors the REST surface's ``require_cmcp_enabled`` 403.
- Bad input shape (Pydantic ``ValidationError``) → re-raised as
  :class:`MCPToolValidationError` carrying the structured ``errors()``
  list as ``details`` so the dispatcher emits a FastAPI-compatible 422.
- Non-mapping ``arguments`` → :class:`MCPToolValidationError` (422).
- Subject / strand resolution miss → ``HTTPException(422)`` raised by
  :func:`generate_cmcp_preview_sync` — left as-is because that helper
  is a route-layer collaborator (the REST surface uses the same path
  and we don't own its exception contract from here).
- Empty CEG SE list for the request → ``HTTPException(422)`` (same).
- ``NoCurriculumMatchError`` from the engine → ``HTTPException(422)``
  (same).
- Anything else bubbles up to the route layer's 500 path.

Why we still let ``HTTPException`` propagate from
``generate_cmcp_preview_sync``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The CB-CMCP-001 REST route (``POST /api/cmcp/generate``) and this MCP
tool share that helper byte-for-byte. Re-translating its
``HTTPException(422)`` into :class:`MCPToolValidationError` here would
mean catching every variant the helper might raise, which couples this
module to the helper's internal error vocabulary. The dispatcher
already handles ``HTTPException`` cleanly (FastAPI's default error
machinery), so leaving those bubbles up keeps the helper as the single
source of truth for its own contract.
"""
from __future__ import annotations

from typing import Any, Mapping

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.routes.cmcp_generate import generate_cmcp_preview_sync
from app.mcp.tools._errors import (
    MCPToolAccessDeniedError,
    MCPToolValidationError,
)
from app.models.user import User
from app.schemas.cmcp import CMCPGenerateRequest
from app.services.feature_flag_service import is_feature_enabled

# Flag key the REST route gates on (see ``app.api.routes.curriculum``'s
# ``require_cmcp_enabled``). The MCP transport gates on its own
# ``mcp.enabled`` flag, but the curriculum-content surface this tool
# wraps is the *same* surface the REST route guards — so an admin
# turning ``cmcp.enabled`` OFF must disable BOTH transports, not just
# the REST one. Re-check it here instead of duplicating the route's
# ``require_cmcp_enabled`` dependency machinery (the dispatcher already
# resolved auth + ``mcp.enabled``; we only need the curriculum flag).
_CMCP_FEATURE_FLAG_KEY = "cmcp.enabled"


def generate_content_handler(
    arguments: Mapping[str, Any],
    current_user: User,
    db: Session,
) -> dict[str, Any]:
    """Build a CEG-anchored generation preview from MCP-supplied arguments.

    Validates *arguments* against :class:`CMCPGenerateRequest` (the
    same body shape as ``POST /api/cmcp/generate``), then delegates to
    :func:`generate_cmcp_preview_sync`. The return value is the
    ``GenerationPreview.model_dump()`` form so the dispatcher can
    JSON-serialize it directly into the ``CallToolResponse.content``
    field without re-validating.

    Args:
        arguments: Raw MCP ``arguments`` dict from the call_tool body.
            Must conform to ``CMCPGenerateRequest``'s JSON Schema
            (declared on the parent ``TOOLS["generate_content"]``
            descriptor's ``input_schema``).
        current_user: Authoritative ``User`` row resolved by the route
            layer's ``require_mcp_enabled`` dependency. The MCP
            registry has already verified the caller's role is in this
            tool's allowlist (TEACHER + ADMIN); this handler does NOT
            re-check role membership — defense-in-depth lives in the
            dispatcher.
        db: Live ``Session`` from the route layer's ``get_db``
            dependency.

    Returns:
        ``GenerationPreview`` as a dict (``model_dump()`` form). Keys
        match the REST route exactly: ``prompt``, ``se_codes_targeted``,
        ``voice_module_id``, ``voice_module_hash``, ``persona``.

    Raises:
        MCPToolAccessDeniedError: 403 when ``cmcp.enabled`` is OFF.
        MCPToolValidationError: 422 on input-validation failures (bad
            arguments shape, Pydantic schema mismatch).
        HTTPException: 422 from
            :func:`generate_cmcp_preview_sync` for curriculum-resolution
            misses (left untouched — that helper is the REST surface's
            collaborator and owns its own contract).
        Non-HTTP errors (e.g., DB failure) bubble up so the MCP route
        layer's 500 path catches them.
    """
    # Curriculum-flag gate — defense-in-depth over the route's
    # ``require_cmcp_enabled`` (#4561 review pass-1). The MCP
    # dispatcher only checks ``mcp.enabled``; without this re-check an
    # admin flipping ``cmcp.enabled`` OFF would disable the REST
    # surface but leave the MCP path serving content. We mirror the
    # route's 403 status so the failure looks identical on both
    # transports — the dispatcher translates
    # :class:`MCPToolAccessDeniedError` to 403.
    if not is_feature_enabled(_CMCP_FEATURE_FLAG_KEY, db=db):
        raise MCPToolAccessDeniedError(
            "CB-CMCP-001 generation is disabled (cmcp.enabled OFF)"
        )

    # Type guard — ``CMCPGenerateRequest.model_validate`` accepts
    # ``Any`` and would surface a confusing per-field error if the
    # caller sent a list or scalar instead of a JSON object. The MCP
    # transport's ``CallToolRequest.arguments`` is already typed
    # ``dict``, but defending here keeps direct service-layer callers
    # honest (#4561 review pass-1).
    if not isinstance(arguments, Mapping):
        raise MCPToolValidationError("arguments must be a JSON object")

    # Input validation via the existing Pydantic schema. We deliberately
    # round-trip through ``model_validate`` rather than the route's
    # automatic body-parse path — the MCP transport hands us a dict
    # straight from JSON, with no FastAPI-side validation. Surfacing
    # validation errors as 422 keeps the MCP error shape aligned with
    # the REST surface ("bad input" looks the same on both transports).
    try:
        payload = CMCPGenerateRequest.model_validate(arguments)
    except ValidationError as exc:
        # ``exc.errors()`` is the structured Pydantic error list — pass
        # it through verbatim via the ``details`` keyword so MCP
        # clients can highlight the offending field. The dispatcher
        # uses ``details`` (when present) as the HTTP body's ``detail``
        # field, matching FastAPI's own 422 shape.
        raise MCPToolValidationError(
            "Invalid arguments",
            details=exc.errors(),
        ) from exc

    preview = generate_cmcp_preview_sync(
        payload=payload,
        current_user=current_user,
        db=db,
    )
    # ``model_dump(mode='json')`` (not the default mode) — coerces any
    # non-JSON-native types (datetime, UUID, Decimal, enum) to JSON
    # primitives at the service-layer boundary. ``GenerationPreview``
    # is JSON-native today, but the cost on a 5-field model is
    # negligible and it future-proofs the boundary against schema
    # evolution: a future field that's e.g. ``datetime`` would
    # otherwise fail at FastAPI's response-serialization layer with a
    # 500 instead of being coerced cleanly here (#4561 review pass-1).
    return preview.model_dump(mode="json")


__all__ = ["generate_content_handler"]
