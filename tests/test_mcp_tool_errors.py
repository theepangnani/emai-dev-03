"""Unit tests for the shared MCP tool exception types.

CB-CMCP-001 M2 follow-up (#4566) — verify each exception subclasses
the expected built-in (so callers writing ``except LookupError`` etc.
still catch them) and that the ``details`` payload on
:class:`MCPToolValidationError` round-trips through.

These are pure-Python unit tests; no DB / no FastAPI client / no MCP
dispatcher in the loop. The end-to-end "raise → HTTP code" coverage
lives in :mod:`tests.test_mcp_routes` (dispatcher) +
:mod:`tests.test_mcp_get_artifact` /
:mod:`tests.test_mcp_list_catalog` /
:mod:`tests.test_mcp_generate_content` (per-tool integration shape).

Imports are inside each test (rather than at module top) to match the
project convention for MCP tool tests — the session-scoped ``app``
fixture in ``conftest.py`` reloads ``app.models`` between modules, and
module-top imports of any ``app.*`` symbol from a tool module cached
the wrong DB/auth state in this run, breaking downstream test files
(see #4566 PR — agent surfaced this in the focused MCP suite).
"""
from __future__ import annotations

import pytest


def test_not_found_subclasses_lookup_error():
    """``MCPToolNotFoundError`` is a ``LookupError``.

    Mutation-test guard — if someone changes the base class to plain
    ``Exception`` a downstream caller's ``except LookupError`` clause
    would silently stop catching the MCP variant.
    """
    from app.mcp.tools._errors import MCPToolNotFoundError

    assert issubclass(MCPToolNotFoundError, LookupError)
    with pytest.raises(LookupError):
        raise MCPToolNotFoundError("missing")


def test_access_denied_subclasses_permission_error():
    """``MCPToolAccessDeniedError`` is a ``PermissionError``."""
    from app.mcp.tools._errors import MCPToolAccessDeniedError

    assert issubclass(MCPToolAccessDeniedError, PermissionError)
    with pytest.raises(PermissionError):
        raise MCPToolAccessDeniedError("denied")


def test_validation_error_subclasses_value_error():
    """``MCPToolValidationError`` is a ``ValueError``."""
    from app.mcp.tools._errors import MCPToolValidationError

    assert issubclass(MCPToolValidationError, ValueError)
    with pytest.raises(ValueError):
        raise MCPToolValidationError("bad")


def test_validation_error_message_round_trip():
    """The message passed to ``__init__`` is recoverable via ``str``."""
    from app.mcp.tools._errors import MCPToolValidationError

    exc = MCPToolValidationError("limit must be between 1 and 100")
    assert "between 1 and 100" in str(exc)
    # No structured payload by default — dispatcher falls back to
    # ``str(exc)`` when ``details`` is None.
    assert exc.details is None


def test_validation_error_details_payload():
    """``details=`` keyword preserves a structured per-field payload.

    Mirrors how :mod:`app.mcp.tools.generate_content` forwards
    Pydantic's ``ValidationError.errors()`` list.
    """
    from app.mcp.tools._errors import MCPToolValidationError

    structured = [
        {"loc": ["body", "subject_code"], "msg": "field required"}
    ]
    exc = MCPToolValidationError("Invalid arguments", details=structured)
    assert exc.details is structured
    # Message is still recoverable separately so logs that just use
    # ``str(exc)`` keep their old shape.
    assert str(exc) == "Invalid arguments"


def test_validation_error_default_message_when_none():
    """Default empty-string message is safe to ``str``."""
    from app.mcp.tools._errors import MCPToolValidationError

    exc = MCPToolValidationError(details={"k": "v"})
    # ``str(exc)`` is empty when no message — the dispatcher prefers
    # ``details`` when present, so the empty-message path is fine.
    assert str(exc) == ""
    assert exc.details == {"k": "v"}
