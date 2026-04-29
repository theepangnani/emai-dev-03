"""Shared visibility helpers for MCP tools (CB-CMCP-001 M2 followup #4567).

Centralizes board-scope resolution so 2B-2 (get_artifact) and 2B-3
(list_catalog) — and any future role-scoped MCP tools — use one
implementation. M3-E will add a real ``User.board_id`` column; the
update lands here, not in N tool files.
"""
from typing import Any


def resolve_caller_board_id(user: Any) -> str | None:
    """Best-effort board-scope resolver for MCP tool visibility filters.

    Returns ``None`` when:

    - User row has no ``board_id`` attribute (current state, until M3-E)
    - User is a system / service account with no board affiliation

    Tools that consume this should use the returned ``None`` to gate
    their BOARD_ADMIN visibility branch — typically by failing closed
    (denying access) rather than broadening to all rows. This mirrors
    the rest of the app's "deny by default until the data shape catches
    up" pattern (see ``can_access_parent_companion`` in
    ``app/api/deps.py``).
    """
    return getattr(user, "board_id", None)


__all__ = ["resolve_caller_board_id"]
