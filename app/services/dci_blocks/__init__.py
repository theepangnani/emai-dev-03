"""CB-DCI-001 block-renderer registry.

Block renderers produce typed payload dicts for the Daily Check-In
ingest contract. Each renderer is a pure function over (artifact_id,
kid_id, db) → ``dict | None`` — returning ``None`` means the block is
omitted from the day's check-in (not an error).

The registry is keyed by ``block_type`` (the same string that lands in
the rendered payload's ``block_type`` field) so the surface dispatcher
(CB-CMCP-001 3C-1, Wave 2) can fan out one block per artifact without
hard-coding the import path.

CB-CMCP-001 3C-2 (#4579) registers the first block —
``cb_cmcp_coach_card`` — which renders a 5-min coach card from a
parent-persona CMCP artifact.
"""
from __future__ import annotations

from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.services.dci_blocks.cmcp_coach_card import (
    CMCP_COACH_CARD_BLOCK_TYPE,
    render_cmcp_coach_card,
)

# Renderer signature — every block renderer accepts the same triplet so
# the dispatcher can resolve + invoke without per-type branching.
BlockRenderer = Callable[[int, int, Session], Optional[dict]]


_BLOCK_REGISTRY: dict[str, BlockRenderer] = {
    CMCP_COACH_CARD_BLOCK_TYPE: render_cmcp_coach_card,
}


def register_block(block_type: str, renderer: BlockRenderer) -> None:
    """Register a new block renderer under ``block_type``.

    Idempotent: re-registering the same renderer for the same key is a
    no-op. Re-registering a *different* renderer for the same key
    raises — block types must be unique to keep the dispatcher
    deterministic.
    """
    existing = _BLOCK_REGISTRY.get(block_type)
    if existing is None:
        _BLOCK_REGISTRY[block_type] = renderer
        return
    if existing is renderer:
        return
    raise ValueError(
        f"DCI block_type {block_type!r} already registered to a "
        "different renderer"
    )


def get_block_renderer(block_type: str) -> BlockRenderer | None:
    """Return the registered renderer for ``block_type`` or ``None``."""
    return _BLOCK_REGISTRY.get(block_type)


def registered_block_types() -> list[str]:
    """Return a sorted list of registered block_type keys.

    Sorted output is intentional for deterministic dispatcher ordering
    + stable test assertions.
    """
    return sorted(_BLOCK_REGISTRY.keys())


__all__ = [
    "BlockRenderer",
    "CMCP_COACH_CARD_BLOCK_TYPE",
    "get_block_renderer",
    "register_block",
    "registered_block_types",
    "render_cmcp_coach_card",
]
