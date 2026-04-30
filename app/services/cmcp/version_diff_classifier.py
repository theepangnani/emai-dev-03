"""CEG version diff severity classifier — pure logic, no DB or I/O.

CB-CMCP-001 M3-G 3G-1 (#4657). Per locked decision D9=B: when a new
``CurriculumVersion`` lands, each Specific Expectation (SE) row is diffed
against its prior-version counterpart and classified into one of two
severities:

- ``wording_only``       — rephrase / punctuation / minor edit; downstream
                           artifacts are NOT reflagged.
- ``scope_substantive``  — material change to scope (text, code, or
                           parent-OE attachment); drives the
                           ``ArtifactReClassified`` domain event in stripe
                           3G-2 (artifact cascade).

The two valid output strings are pinned by the
``ck_curriculum_versions_change_severity`` CHECK constraint on the
``curriculum_versions.change_severity`` column (see
``app/models/curriculum.py`` — the column already exists from M0-A 0A-1,
so no migration is needed in this stripe).

Heuristic (per issue #4657 acceptance criteria):

1. ``cb_code`` differs                                  → ``scope_substantive``
2. ``parent_oe_id`` differs                             → ``scope_substantive``
3. ``expectation_text`` token-set difference > 30%      → ``scope_substantive``
4. otherwise                                            → ``wording_only``

The function accepts either dict-shaped SE rows (e.g., the MCP
``get_expectations`` payload — keys ``expectation_text``, ``cb_code``,
``parent_oe_id``) or any object exposing the same attribute names. Both
inputs MUST have these three fields populated; missing fields are read as
``None`` and compared by equality (so ``None vs "X"`` registers as a
``cb_code`` change → ``scope_substantive``).

Stripe 3G-2 (artifact cascade) DEPENDS on this classifier — it iterates
the SE-pair diff and reflags only artifacts whose pinned SE rows came
back ``scope_substantive``.
"""
from __future__ import annotations

import re
from typing import Any

# --- Output sentinels --------------------------------------------------------
# Re-exported here so callers (3G-2 cascade, tests) don't have to reach into
# the model module just to compare strings.
SEVERITY_WORDING_ONLY = "wording_only"
SEVERITY_SCOPE_SUBSTANTIVE = "scope_substantive"

# --- Heuristic threshold -----------------------------------------------------
# Issue #4657 spec: > 30% token-set difference in expectation text counts as
# substantive. We use Jaccard distance over case-folded word tokens. This
# avoids the O(N*M) cost of a true Levenshtein on long expectation strings
# (Ontario SE descriptions can run 60+ words) while still catching the
# rephrase-vs-rewrite distinction the spec is targeting:
#
#   "describe the water cycle"  vs  "describe the water cycle in detail"
#       → Jaccard distance ≈ 0.29 → wording_only (boundary case)
#
#   "describe the water cycle"  vs  "model evaporation and condensation"
#       → Jaccard distance = 1.0  → scope_substantive
#
# The threshold is exclusive (``> 0.30``) so a clean 30% rewrite still
# classifies as ``wording_only``; only edits that exceed 30% trip
# ``scope_substantive``. This matches the issue's "changes >30%" wording.
TEXT_DIFF_THRESHOLD = 0.30

# Word tokenizer — matches sequences of word characters (letters, digits,
# underscores) and apostrophes inside words (so "student's" stays one token).
# Punctuation, whitespace, and stray symbols are dropped, which is exactly
# what we want for a "wording only" rephrase to register as low-distance.
_WORD_RE = re.compile(r"[A-Za-z0-9_]+(?:'[A-Za-z0-9_]+)?")


def _get(se: Any, key: str) -> Any:
    """Read ``key`` from ``se`` whether it's a dict or an attribute-bearing
    object. Returns ``None`` if missing — callers compare by equality, so
    a missing field on one side registers as a change."""
    if se is None:
        return None
    if isinstance(se, dict):
        return se.get(key)
    return getattr(se, key, None)


def _tokenize(text: str | None) -> set[str]:
    """Lowercase + tokenize ``text`` into a set of word tokens. Returns an
    empty set for ``None`` or empty input. Set semantics (not list) —
    identical to "token-set ratio" from the issue spec; word-order changes
    don't register as a diff, but vocabulary changes do."""
    if not text:
        return set()
    return {m.group(0).lower() for m in _WORD_RE.finditer(text)}


def _token_set_distance(old_text: str | None, new_text: str | None) -> float:
    """Jaccard distance between the token sets of two expectation texts,
    in ``[0.0, 1.0]``. ``0.0`` = identical token sets; ``1.0`` = disjoint.

    Two empty/None inputs collapse to ``0.0`` (no change to flag — see the
    "identical SEs" edge case in the issue). One empty + one non-empty
    yields ``1.0`` (full vocabulary change → substantive)."""
    old_tokens = _tokenize(old_text)
    new_tokens = _tokenize(new_text)
    if not old_tokens and not new_tokens:
        return 0.0
    union = old_tokens | new_tokens
    if not union:  # defensive: both empty handled above, but guard anyway
        return 0.0
    intersection = old_tokens & new_tokens
    return 1.0 - (len(intersection) / len(union))


def classify_se_change(old_se: Any, new_se: Any) -> str:
    """Classify an SE-level change as ``wording_only`` or ``scope_substantive``.

    Args:
        old_se: Prior-version SE row. Dict with keys ``expectation_text``,
            ``cb_code``, ``parent_oe_id`` OR an object with those
            attributes (e.g., a ``CEGExpectation`` ORM instance using
            ``description`` would NOT match — caller must adapt to the
            ``expectation_text`` key/attr name).
        new_se: New-version SE row, same shape as ``old_se``.

    Returns:
        Either :data:`SEVERITY_WORDING_ONLY` or
        :data:`SEVERITY_SCOPE_SUBSTANTIVE`. The string values match the
        ``ck_curriculum_versions_change_severity`` CHECK constraint on
        ``curriculum_versions.change_severity``.

    Edge cases:

    - ``old_se is None`` or ``new_se is None`` — treated as full change
      (cb_code reads as ``None`` on the missing side, so a non-None
      ``cb_code`` on the other side trips substantive). If BOTH are
      ``None`` (degenerate caller bug), we collapse to ``wording_only``
      since there is, definitionally, no change to classify.
    - Identical SEs — all three fields equal → ``wording_only``.
    - Whitespace-only or punctuation-only edits to ``expectation_text`` —
      tokenizer drops both; distance = 0.0 → ``wording_only``.
    """
    # Both-None degenerate: no SE pair to compare, no change to flag.
    if old_se is None and new_se is None:
        return SEVERITY_WORDING_ONLY

    # 1. cb_code change — substantive (curriculum re-coding always reflags).
    old_code = _get(old_se, "cb_code")
    new_code = _get(new_se, "cb_code")
    if old_code != new_code:
        return SEVERITY_SCOPE_SUBSTANTIVE

    # 2. parent_oe_id change — substantive (SE moved under a different OE).
    old_parent = _get(old_se, "parent_oe_id")
    new_parent = _get(new_se, "parent_oe_id")
    if old_parent != new_parent:
        return SEVERITY_SCOPE_SUBSTANTIVE

    # 3. expectation_text token-set distance > threshold — substantive.
    old_text = _get(old_se, "expectation_text")
    new_text = _get(new_se, "expectation_text")
    if _token_set_distance(old_text, new_text) > TEXT_DIFF_THRESHOLD:
        return SEVERITY_SCOPE_SUBSTANTIVE

    # 4. Otherwise — wording-only (no downstream reflag).
    return SEVERITY_WORDING_ONLY
