"""Known school-board domains used by the unified-digest attribution heuristic.

Adding a board:
- Append to KNOWN_SCHOOL_BOARD_DOMAINS below.
- No migration, no deploy gating — picked up automatically on next import.
- Domain MUST be lower-cased and represent the apex (suffix-match handles
  subdomains automatically — see is_school_looking_address).

Why a Python module not YAML/DB:
- Zero parser/connection dependency at module import time.
- Deterministic — no startup-order surprises.
- Plain text, easy diff in code review.
- DB-table option is over-engineering for a 9-row list.

If this list grows beyond ~200 entries, revisit the shape (DB table seeded
at startup, queryable per-request).
"""
from __future__ import annotations

# Frozenset for O(1) membership lookup. Lower-case, apex domain only.
KNOWN_SCHOOL_BOARD_DOMAINS: frozenset[str] = frozenset({
    # Ontario
    "ocdsb.ca",
    "tdsb.on.ca",
    "peelschools.org",
    "dsbn.org",
    "yrdsb.ca",
    "dpcdsb.org",
    "hwdsb.on.ca",
    "wrdsb.ca",
    # British Columbia
    "sd35.bc.ca",
})
