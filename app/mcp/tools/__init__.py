"""MCP tool registry + dispatcher.

CB-CMCP-001 M2-A 2A-2 (#4550) — initial port from ``class-bridge-phase-2``.

Stripe scope
------------
This stripe lands the registry/dispatcher *shape* the MCP transport
endpoints (:mod:`app.mcp.routes`) call into. Concrete tool
implementations land in 2B-1..2B-4:

- ``get_expectations``  — 2B-1
- ``get_artifact``      — 2B-2
- ``list_catalog``      — 2B-3
- ``generate_content``  — 2B-4

Until those land, every tool entry's ``handler`` is :func:`_stub_handler`,
which raises an :class:`MCPNotImplementedError` so the route layer can
return ``501 Not Implemented`` without ambiguity.

Why a hand-rolled registry (not ``fastapi_mcp``)
------------------------------------------------
``fastapi_mcp`` is not in dev-03's ``requirements.txt`` and adopting it
would (a) drag in a transitive dependency surface we haven't vetted and
(b) couple our tool catalog to FastAPI route operationIds rather than
explicit MCP tool names. The MCP transport surface for CB-CMCP-001 is
small (4 tools + a couple control endpoints), so a native registry is
cheaper to maintain and easier to audit.

Role-based access
-----------------
Each tool declares a ``roles`` allowlist (list of role *names*, normalized
uppercase to match :data:`app.mcp.auth.ROLE_TOOLS` conventions). The
route layer filters the catalog by the caller's authoritative role
(resolved from the ``User`` row, never the JWT claim — see 2A-1's
``MCPSession.role`` caveat) before returning it, and re-checks role
membership in :func:`call_tool` to defend against catalog/dispatch skew.

Adding a tool
-------------
1. Implement a callable matching :class:`ToolHandler` — i.e. it accepts
   ``(arguments: dict, current_user: User, db: Session)`` and returns a
   JSON-serializable dict.
2. Register it in :data:`TOOLS` with a stable ``name``, a one-sentence
   ``description``, an ``input_schema`` dict (JSON Schema), and the role
   allowlist.
3. Replace the existing stub entry rather than appending a new one — the
   tool name is the dispatch key.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

# CB-CMCP-001 M2-B 2B-2 (#4553) — concrete handler for ``get_artifact``.
from app.mcp.tools.get_artifact import get_artifact_handler

# CB-CMCP-001 M2-B 2B-4 (#4555) — concrete handler for ``generate_content``.
from app.mcp.tools.generate_content import generate_content_handler

# CB-CMCP-001 M2-B 2B-1 (#4552) — concrete handler for ``get_expectations``.
from app.mcp.tools.get_expectations import get_expectations_handler

# ---------------------------------------------------------------------------
# Stub error
# ---------------------------------------------------------------------------


class MCPNotImplementedError(NotImplementedError):
    """Raised by stub tool handlers — surfaced as ``501`` by the route layer.

    The route layer catches this specifically so that *unimplemented* tool
    invocations return a deterministic 501 with the tool name in the
    detail, while other ``NotImplementedError``s (e.g. raised inside a
    later 2B-* implementation by mistake) bubble up as 500s.
    """


def _stub_handler(tool_name: str) -> Callable[..., Any]:
    """Return a handler that always raises :class:`MCPNotImplementedError`.

    Closes over *tool_name* so the error message identifies which tool the
    caller asked for. Used in :data:`TOOLS` for the four 2B-* placeholders
    until those stripes land.
    """

    def _raise(arguments: Mapping[str, Any], current_user: Any, db: Any) -> Any:
        # Signature matches :class:`ToolHandler`. We accept and discard
        # *arguments* / *current_user* / *db* so the dispatcher can call
        # every registered handler the same way.
        del arguments, current_user, db
        raise MCPNotImplementedError(
            f"MCP tool '{tool_name}' is not yet implemented "
            "(stripes 2B-1..2B-4 land in CB-CMCP-001 M2 Wave 3)."
        )

    return _raise


# ---------------------------------------------------------------------------
# Tool descriptor
# ---------------------------------------------------------------------------


# Type alias for a tool handler. Kept loose (``Any`` for User / Session) so
# the registry module doesn't import the SQLAlchemy / model layer at import
# time — the route layer passes the resolved instances through.
ToolHandler = Callable[[Mapping[str, Any], Any, Any], Any]


@dataclass(frozen=True)
class ToolDescriptor:
    """Metadata + dispatch entry for a single MCP tool.

    Frozen so the registry can't be mutated by callers at runtime; mutate
    by editing :data:`TOOLS` and shipping a new release. ``input_schema``
    is a plain dict (not a ``BaseModel``) because MCP clients consume it
    as JSON Schema directly — Pydantic adds no value here.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    roles: tuple[str, ...]
    handler: ToolHandler = field(repr=False, compare=False)
    # Precomputed normalized allowlist (#4559 review pass-1). Built in
    # ``__post_init__`` so :meth:`is_role_allowed` can do an O(1) hash
    # lookup on every catalog request and dispatch call without
    # rebuilding a set comprehension. ``init=False`` so the registry's
    # construction sites don't have to pass it; ``compare=False`` so
    # equality stays driven by the user-visible fields.
    _normalized_roles: frozenset[str] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        """Compute :attr:`_normalized_roles` once at construction time.

        Frozen dataclasses block normal attribute assignment, so we go
        through ``object.__setattr__`` — the standard escape hatch for
        ``__post_init__`` on a frozen dataclass.
        """
        object.__setattr__(
            self,
            "_normalized_roles",
            frozenset(r.strip().upper() for r in self.roles),
        )

    def is_role_allowed(self, role: str | None) -> bool:
        """Return ``True`` iff *role* (case-insensitive) is in the allowlist.

        Empty / ``None`` roles always fail. ``ADMIN`` is intentionally
        treated like any other role here — admins must be listed in each
        tool's ``roles`` tuple if they should see it. (The phase-2
        ``ROLE_TOOLS`` admin-bypass sentinel applies only to that
        endpoint-tool surface, not to the 2B-* MCP tools.)

        O(1) on the precomputed :attr:`_normalized_roles` frozenset
        (#4559 review pass-1) — called twice per ``call_tool`` request
        (catalog filter + dispatch re-check) so the per-call cost
        matters as more tools land in 2B-*.
        """
        if not role:
            return False
        return role.strip().upper() in self._normalized_roles

    def to_public_dict(self) -> dict[str, Any]:
        """Return the JSON-safe form for ``GET /mcp/list_tools``.

        Excludes ``handler`` (not JSON-serializable) and ``roles`` (a
        server-side concern — leaking the full allowlist would let
        unauthorized callers infer which tools exist for other roles).
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


def _list_catalog_handler(
    arguments: Mapping[str, Any], current_user: Any, db: Any
) -> Any:
    """Thin wrapper that defers the import of ``list_catalog.list_catalog``.

    CB-CMCP-001 M2-B 2B-3 (#4554). The concrete handler lives in
    :mod:`app.mcp.tools.list_catalog`; importing it at module top would
    drag the SQLAlchemy model layer into this registry's import path
    (the registry is intentionally model-free — see module docstring).
    The wrapper keeps the registry import-light and lets the conftest
    model-reload pattern continue to work without re-entering this
    module.
    """
    from app.mcp.tools.list_catalog import list_catalog as _impl

    return _impl(arguments, current_user, db)


# ---------------------------------------------------------------------------
# Stub tool registry — 2B-1..2B-4 placeholders
# ---------------------------------------------------------------------------
#
# Each entry uses ``_stub_handler(name)`` so calling the tool deterministically
# raises :class:`MCPNotImplementedError`. The route layer catches it and
# returns 501. The role allowlists below are the minimal set per the
# CB-CMCP-001 design notes; 2A-3 may extend them with BOARD_ADMIN /
# CURRICULUM_ADMIN entries when those roles' tool surfaces are settled.

TOOLS: dict[str, ToolDescriptor] = {
    "get_expectations": ToolDescriptor(
        name="get_expectations",
        description=(
            "Return the Ontario CEG expectations (overall + specific) for a "
            "given subject + grade + optional strand. Read-only."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "subject_code": {"type": "string"},
                "grade": {"type": "integer"},
                "strand_code": {"type": ["string", "null"]},
            },
            "required": ["subject_code", "grade"],
            "additionalProperties": False,
        },
        roles=("PARENT", "STUDENT", "TEACHER", "ADMIN"),
        handler=get_expectations_handler,
    ),
    "get_artifact": ToolDescriptor(
        name="get_artifact",
        description=(
            "Fetch a single CB-CMCP content artifact by id. Access is "
            "subject to the FR-05 access matrix."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "artifact_id": {"type": "integer"},
            },
            "required": ["artifact_id"],
            "additionalProperties": False,
        },
        # 2B-2 (#4553) — extended to BOARD_ADMIN + CURRICULUM_ADMIN per
        # the issue's role scope: those roles need read access for
        # catalog + curriculum work. The handler enforces per-row
        # visibility (board scoping for BOARD_ADMIN, all-access for
        # CURRICULUM_ADMIN), so the catalog allowlist can safely
        # include them.
        roles=(
            "PARENT",
            "STUDENT",
            "TEACHER",
            "BOARD_ADMIN",
            "CURRICULUM_ADMIN",
            "ADMIN",
        ),
        handler=get_artifact_handler,
    ),
    "list_catalog": ToolDescriptor(
        name="list_catalog",
        description=(
            "List APPROVED CB-CMCP content artifacts the caller may access, "
            "optionally filtered by subject / grade / strand. Cursor-paginated. "
            "IMPORTANT: an empty 'artifacts' array does NOT mean 'no more results' — "
            "callers must check 'next_cursor is None' to detect end of iteration. "
            "(Post-filtering on subject/grade can return 0 matches in a window with "
            "non-null next_cursor; M3 will add a real grade column and restore "
            "standard cursor semantics.)"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "subject_code": {"type": ["string", "null"]},
                "grade": {"type": ["integer", "null"]},
                "state": {
                    "type": ["string", "null"],
                    "default": "APPROVED",
                },
                "content_type": {"type": ["string", "null"]},
                "cursor": {"type": ["string", "null"]},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                },
            },
            "additionalProperties": False,
        },
        roles=(
            "PARENT",
            "STUDENT",
            "TEACHER",
            "BOARD_ADMIN",
            "CURRICULUM_ADMIN",
            "ADMIN",
        ),
        handler=_list_catalog_handler,
    ),
    "generate_content": ToolDescriptor(
        name="generate_content",
        description=(
            "Build a CEG-anchored generation prompt + return the preview. "
            "Wraps POST /api/cmcp/generate behind the MCP transport. "
            "TEACHER + ADMIN only."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "subject_code": {"type": "string"},
                "strand_code": {"type": "string"},
                "grade": {"type": "integer"},
                "content_type": {
                    "type": "string",
                    "enum": [
                        "STUDY_GUIDE",
                        "WORKSHEET",
                        "QUIZ",
                        "SAMPLE_TEST",
                        "ASSIGNMENT",
                        "PARENT_COMPANION",
                    ],
                },
                "difficulty": {
                    "type": "string",
                    "enum": ["APPROACHING", "GRADE_LEVEL", "EXTENDING"],
                },
                "topic": {"type": ["string", "null"]},
                "course_id": {"type": ["integer", "null"]},
            },
            "required": [
                "subject_code",
                "strand_code",
                "grade",
                "content_type",
                "difficulty",
            ],
            "additionalProperties": False,
        },
        roles=("TEACHER", "ADMIN"),
        # CB-CMCP-001 M2-B 2B-4 (#4555): wire the real handler. The
        # PARENT/STUDENT self-study generation path (D3=C in the locked
        # design) is intentionally deferred to M3-B — keeping the role
        # tuple narrow (TEACHER + ADMIN) here means M2 ships exactly the
        # surface the M1 REST route already exposes, with no scope creep
        # into multi-persona templates the M3-B sub-stripes own.
        handler=generate_content_handler,
    ),
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_tool(name: str) -> ToolDescriptor | None:
    """Return the registered tool for *name*, or ``None`` if unknown.

    Lookup is case-sensitive — MCP tool names are stable identifiers and
    case-insensitive matching would mask typos in the registry.
    """
    return TOOLS.get(name)


def list_tools_for_role(role: str | None) -> list[ToolDescriptor]:
    """Return tools the given role may invoke.

    Empty list when *role* is missing / unknown. Order is deterministic
    (registry insertion order) so MCP clients and snapshot tests both
    see a stable catalog.
    """
    return [t for t in TOOLS.values() if t.is_role_allowed(role)]


__all__ = [
    "MCPNotImplementedError",
    "TOOLS",
    "ToolDescriptor",
    "ToolHandler",
    "get_tool",
    "list_tools_for_role",
]
