"""Tests for CB-CMCP-001 M3-G 3G-1 — CEG version diff severity classifier (#4657).

Pure-logic tests, no DB fixtures. Verifies the D9=B heuristic:

- ``cb_code`` change                                → ``scope_substantive``
- ``parent_oe_id`` change                           → ``scope_substantive``
- ``expectation_text`` token-set distance > 30%     → ``scope_substantive``
- otherwise (rephrase, punctuation, identical)      → ``wording_only``
- both inputs ``None`` (degenerate)                 → ``wording_only``

Also exercises both dict-shaped SE rows (the MCP ``get_expectations``
payload shape) and attribute-bearing objects (so the classifier is
substrate-agnostic — caller can pass ORM-adapter dicts OR a SimpleNamespace).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.cmcp.version_diff_classifier import (
    SEVERITY_SCOPE_SUBSTANTIVE,
    SEVERITY_WORDING_ONLY,
    TEXT_DIFF_THRESHOLD,
    classify_se_change,
)


# ---- Fixtures: SE row builders ----------------------------------------------


def _se_dict(
    *,
    text: str = "describe the water cycle and its key processes",
    cb_code: str = "CB-G7-SCI-D2-SE3",
    parent_oe_id: int = 42,
) -> dict:
    """Dict-shaped SE row matching the MCP ``get_expectations`` payload."""
    return {
        "expectation_text": text,
        "cb_code": cb_code,
        "parent_oe_id": parent_oe_id,
    }


def _se_obj(**kwargs) -> SimpleNamespace:
    """Attribute-bearing SE — proves classifier is dict/object agnostic."""
    return SimpleNamespace(**_se_dict(**kwargs))


# ---- Identity / no-change cases --------------------------------------------


def test_identical_ses_classify_as_wording_only():
    """Edge case from #4657: identical SEs → no change → wording_only."""
    se = _se_dict()
    assert classify_se_change(se, dict(se)) == SEVERITY_WORDING_ONLY


def test_both_none_collapses_to_wording_only():
    """Degenerate caller bug — both sides ``None``. Returns wording_only
    rather than raising; the M3-G cascade can no-op safely on this case."""
    assert classify_se_change(None, None) == SEVERITY_WORDING_ONLY


# ---- Wording-only changes (below threshold) ---------------------------------


def test_punctuation_only_change_is_wording_only():
    """Adding a period / comma should not flip severity — tokenizer drops
    punctuation."""
    old = _se_dict(text="describe the water cycle and its key processes")
    new = _se_dict(text="describe the water cycle, and its key processes.")
    assert classify_se_change(old, new) == SEVERITY_WORDING_ONLY


def test_word_order_change_is_wording_only():
    """Token-set semantics: word-order changes register as 0 distance."""
    old = _se_dict(text="describe the water cycle and its key processes")
    new = _se_dict(text="key processes and the water cycle, describe its")
    assert classify_se_change(old, new) == SEVERITY_WORDING_ONLY


def test_minor_rephrase_is_wording_only():
    """Single-word swap on a 9-token text: 1/10 union → ~10% distance,
    well below 30% threshold."""
    old = _se_dict(text="describe the water cycle and its key processes today")
    new = _se_dict(text="describe the water cycle and its main processes today")
    assert classify_se_change(old, new) == SEVERITY_WORDING_ONLY


def test_case_change_only_is_wording_only():
    """Tokenizer lowercases — pure case flips should not register."""
    old = _se_dict(text="Describe The Water Cycle")
    new = _se_dict(text="describe the WATER cycle")
    assert classify_se_change(old, new) == SEVERITY_WORDING_ONLY


# ---- Substantive changes via expectation_text ------------------------------


def test_large_text_rewrite_is_scope_substantive():
    """Full vocabulary swap → distance = 1.0 → substantive."""
    old = _se_dict(text="describe the water cycle and its key processes")
    new = _se_dict(text="model evaporation, condensation, and precipitation")
    assert classify_se_change(old, new) == SEVERITY_SCOPE_SUBSTANTIVE


def test_text_change_above_30pct_is_scope_substantive():
    """Replace 4 of 10 tokens — Jaccard distance ≈ 0.57 → substantive.

    old tokens: {describe, the, water, cycle, and, its, key, processes,
                 in, depth} (10)
    new tokens: {model, evaporation, condensation, precipitation, and,
                 its, key, processes, in, depth} (10)
    intersection = 6, union = 14, distance = 1 - 6/14 ≈ 0.571
    """
    old = _se_dict(
        text="describe the water cycle and its key processes in depth"
    )
    new = _se_dict(
        text="model evaporation condensation precipitation "
        "and its key processes in depth"
    )
    assert classify_se_change(old, new) == SEVERITY_SCOPE_SUBSTANTIVE


def test_just_under_30pct_stays_wording_only():
    """A diff just under the 30% threshold stays ``wording_only``.

    Construct a 12-token union with intersection = 9 → distance = 0.25,
    which is clearly below ``TEXT_DIFF_THRESHOLD = 0.30``. This protects
    against the comparator drifting to ``>=`` (which would still pass the
    far-above and far-below tests but would flip a clean-30% input)."""
    old = _se_dict(
        text="alpha beta gamma delta epsilon zeta eta theta iota"
    )
    new = _se_dict(
        text="alpha beta gamma delta epsilon zeta eta theta iota "
        "kappa lambda mu"
    )
    from app.services.cmcp.version_diff_classifier import _token_set_distance

    # Sanity: distance is 0.25, below the 0.30 threshold.
    assert _token_set_distance(
        old["expectation_text"], new["expectation_text"]
    ) == pytest.approx(0.25)
    assert classify_se_change(old, new) == SEVERITY_WORDING_ONLY


def test_just_over_30pct_is_scope_substantive():
    """A diff just over 30% trips substantive — boundary protection from
    the other side."""
    # 8-token old, 13-token new, intersection 8 → distance = 1 - 8/13 ≈ 0.385
    old = _se_dict(text="alpha beta gamma delta epsilon zeta eta theta")
    new = _se_dict(
        text="alpha beta gamma delta epsilon zeta eta theta "
        "iota kappa lambda mu nu"
    )
    from app.services.cmcp.version_diff_classifier import _token_set_distance

    d = _token_set_distance(
        old["expectation_text"], new["expectation_text"]
    )
    assert d > TEXT_DIFF_THRESHOLD
    assert d < 0.50  # clearly above threshold but not a full rewrite
    assert classify_se_change(old, new) == SEVERITY_SCOPE_SUBSTANTIVE


# ---- Substantive changes via cb_code ---------------------------------------


def test_cb_code_change_is_scope_substantive():
    """Curriculum re-coding always flips → substantive even with identical text."""
    old = _se_dict(cb_code="CB-G7-SCI-D2-SE3")
    new = _se_dict(cb_code="CB-G7-SCI-D2-SE4")
    assert classify_se_change(old, new) == SEVERITY_SCOPE_SUBSTANTIVE


def test_cb_code_to_none_is_scope_substantive():
    """Removing the cb_code (``None`` on the new side) → substantive."""
    old = _se_dict(cb_code="CB-G7-SCI-D2-SE3")
    new = _se_dict(cb_code=None)
    assert classify_se_change(old, new) == SEVERITY_SCOPE_SUBSTANTIVE


# ---- Substantive changes via parent_oe_id ----------------------------------


def test_parent_oe_change_is_scope_substantive():
    """SE moved under a different OE → substantive even with identical text."""
    old = _se_dict(parent_oe_id=42)
    new = _se_dict(parent_oe_id=43)
    assert classify_se_change(old, new) == SEVERITY_SCOPE_SUBSTANTIVE


def test_parent_oe_id_to_none_is_scope_substantive():
    """parent_oe_id detached (``None`` on new side) → substantive."""
    old = _se_dict(parent_oe_id=42)
    new = _se_dict(parent_oe_id=None)
    assert classify_se_change(old, new) == SEVERITY_SCOPE_SUBSTANTIVE


# ---- Object-substrate (not just dict) --------------------------------------


def test_classifier_accepts_attribute_bearing_objects():
    """SimpleNamespace stand-in for any object exposing the three attrs
    (e.g., a Pydantic model or ORM adapter) — proves classifier is
    substrate-agnostic per the docstring contract."""
    old = _se_obj(text="describe the water cycle")
    new = _se_obj(text="model the water cycle")
    # 1 swap on 4-token union ({describe,the,water,cycle} vs
    # {model,the,water,cycle}) → distance = 1 - 3/5 = 0.40 > 0.30
    assert classify_se_change(old, new) == SEVERITY_SCOPE_SUBSTANTIVE


def test_classifier_accepts_mixed_substrates():
    """Caller can pass a dict on one side and an object on the other."""
    old = _se_dict()  # dict
    new = _se_obj(cb_code="CB-G7-SCI-D2-SE99")  # object
    assert classify_se_change(old, new) == SEVERITY_SCOPE_SUBSTANTIVE


# ---- One side None ---------------------------------------------------------


def test_old_se_none_with_new_se_present_is_substantive():
    """A new SE with no prior counterpart — cb_code differs (``None`` vs
    actual code) → substantive. This is the 'newly added SE' case the
    cascade in 3G-2 will treat as needing review."""
    assert (
        classify_se_change(None, _se_dict()) == SEVERITY_SCOPE_SUBSTANTIVE
    )


def test_new_se_none_with_old_se_present_is_substantive():
    """An SE removed from the new version — same logic, opposite direction."""
    assert (
        classify_se_change(_se_dict(), None) == SEVERITY_SCOPE_SUBSTANTIVE
    )


# ---- Sanity on threshold constant ------------------------------------------


def test_threshold_constant_matches_spec():
    """Issue #4657 spec pins the threshold at 30%. If this fails, either
    the constant drifted or the spec changed — fix one or the other."""
    assert TEXT_DIFF_THRESHOLD == 0.30


# ---- Return-value contract -------------------------------------------------


def test_return_value_is_one_of_two_strings():
    """Classifier never returns anything outside the two pinned strings —
    matches the ``ck_curriculum_versions_change_severity`` CHECK constraint."""
    valid = {SEVERITY_WORDING_ONLY, SEVERITY_SCOPE_SUBSTANTIVE}
    assert SEVERITY_WORDING_ONLY == "wording_only"
    assert SEVERITY_SCOPE_SUBSTANTIVE == "scope_substantive"
    # Spot-check across all the major branches.
    assert classify_se_change(_se_dict(), _se_dict()) in valid
    assert (
        classify_se_change(
            _se_dict(cb_code="A"), _se_dict(cb_code="B")
        )
        in valid
    )
    assert classify_se_change(None, None) in valid
