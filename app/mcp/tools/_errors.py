"""Shared domain exception types for MCP tool handlers.

CB-CMCP-001 M2 follow-up (#4566) — standardize the MCP tool error
contract so every tool raises domain exceptions, not ``HTTPException``.

Why domain exceptions (not ``HTTPException``)
---------------------------------------------
The dispatcher in :mod:`app.mcp.routes` (``call_tool``) is the single
translation point from "tool said no" to "HTTP status code". Tools that
raise ``HTTPException`` directly couple themselves to the HTTP transport
— but the MCP spec also defines stdio + SSE transports that future
stripes may add (see plan §M4 follow-on). A tool that raises domain
exceptions can be wired to any transport without code changes; the
transport layer maps the exception to its protocol-native error shape.

Three levels of failure are surfaced today:

- :class:`MCPToolNotFoundError` (404) — the requested resource doesn't
  exist (or arguments referenced an id the catalog can't find).
- :class:`MCPToolAccessDeniedError` (403) — the caller's role allowlists
  the tool but the per-row visibility check denied access.
- :class:`MCPToolValidationError` (422) — the caller's arguments are
  malformed (bad cursor, out-of-range limit, wrong type, etc.).

Each subclasses a built-in (``LookupError`` / ``PermissionError`` /
``ValueError``) so callers writing ``except`` blocks against the
built-in supertypes still catch them — the dispatcher uses the
specific subtype for HTTP status mapping + telemetry.

Related
-------
- :mod:`app.mcp.routes` — translates these exceptions to HTTP responses
  with per-error telemetry hooks.
- :mod:`app.mcp.tools.get_artifact` — first stripe to use this pattern
  (originally with handler-local exception classes; now consolidated
  here per the #4566 review finding).
- :mod:`app.mcp.tools.list_catalog` — migrated from raising
  ``HTTPException`` directly to raising :class:`MCPToolValidationError`.
- :mod:`app.mcp.tools.generate_content` — migrated from raising
  ``HTTPException`` directly to raising the appropriate domain
  exception.
"""
from __future__ import annotations

from typing import Any


class MCPToolNotFoundError(LookupError):
    """Raised when a tool can't find the resource the caller asked for.

    Translated to ``404 Not Found`` by the dispatcher.

    Subclasses :class:`LookupError` so callers writing ``except
    LookupError`` still catch it — useful for callers that don't care
    about the MCP-specific marker but want to handle "not found"
    generically (e.g. retry-with-backoff wrappers around the handler).
    """


class MCPToolAccessDeniedError(PermissionError):
    """Raised when the caller's role disallows visibility to the resource.

    Translated to ``403 Forbidden`` by the dispatcher with a
    ``mcp.call_tool.access_denied`` telemetry hook so operators can
    spot per-row denials separately from catalog-level role denials.

    Subclasses :class:`PermissionError` for the same generic-handler
    reason as :class:`MCPToolNotFoundError`.
    """


class MCPToolValidationError(ValueError):
    """Raised when the caller's tool arguments are malformed.

    Translated to ``422 Unprocessable Entity`` by the dispatcher with a
    ``mcp.call_tool.validation_error`` telemetry hook. Use this for any
    "your arguments are bad" path — bad cursor, out-of-range numeric,
    wrong type, missing required field, etc.

    The optional *details* keyword preserves structured per-field error
    payloads (e.g. Pydantic's ``ValidationError.errors()`` list) so MCP
    clients can highlight the offending field. The dispatcher prefers
    ``details`` over ``str(exc)`` when present so the HTTP body matches
    the FastAPI 422 shape ``generate_content`` previously emitted via a
    raw ``HTTPException(detail=exc.errors())``.

    Subclasses :class:`ValueError` so callers writing ``except
    ValueError`` still catch it.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any = None,
    ) -> None:
        super().__init__(message or "")
        self.details: Any = details


__all__ = [
    "MCPToolAccessDeniedError",
    "MCPToolNotFoundError",
    "MCPToolValidationError",
]
