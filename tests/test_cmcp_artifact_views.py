"""CB-CMCP-001 #4701 — shared artifact-summary projector tests.

Covers :func:`app.services.cmcp._artifact_views.cmcp_artifact_summary_v1`
and the SE-code helpers it builds on. The projector is the single source
of truth for the public summary shape across MCP ``list_catalog`` (M2-B
2B-3) and REST ``board_catalog`` (M3-E 3E-1) — these tests pin the v1
shape so accidental drift is caught at test time, not at integration.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.cmcp._artifact_views import (
    _se_grade,
    _se_subject,
    cmcp_artifact_summary_v1,
)


# ─────────────────────────────────────────────────────────────────────
# SE-helper coverage — preserves the prior behaviour from
# ``app.mcp.tools.list_catalog`` (these were hoisted unchanged).
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "se_codes, expected",
    [
        (["MATH.5.A.1"], "MATH"),
        (["sci.7.b.2"], "SCI"),  # uppercase normalization
        ([], None),
        (None, None),
        (["NO_DOT_HERE"], None),
        ([42], None),  # non-string entry
    ],
)
def test_se_subject(se_codes, expected):
    assert _se_subject(se_codes) == expected


@pytest.mark.parametrize(
    "se_codes, expected",
    [
        (["MATH.5.A.1"], 5),
        (["SCI.10.B.2"], 10),
        ([], None),
        (None, None),
        (["MATH"], None),  # no second segment
        (["MATH.notanum.A"], None),
        ([42], None),
    ],
)
def test_se_grade(se_codes, expected):
    assert _se_grade(se_codes) == expected


# ─────────────────────────────────────────────────────────────────────
# Helpers — fake row factory
# ─────────────────────────────────────────────────────────────────────


def _row(**overrides):
    """Return a ``SimpleNamespace`` that quacks like a ``StudyGuide`` row.

    Only attributes the projector reads need defaults; everything else
    can be overridden per-test.
    """
    base = dict(
        id=42,
        title="Sample Guide",
        guide_type="study_guide",
        state="APPROVED",
        se_codes=["MATH.5.A.1"],
        alignment_score=Decimal("0.876"),
        ai_engine="openai/gpt-4o-mini",
        course_id=11,
        created_at=datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# ─────────────────────────────────────────────────────────────────────
# Projector — happy path + invariants
# ─────────────────────────────────────────────────────────────────────


def test_cmcp_artifact_summary_v1_happy_path_full_shape():
    """v1 shape contract: every public field present + correctly typed.

    This test pins the v1 contract so a future shape change has to bump
    the version (per the module docstring's versioning note).
    """
    row = _row()
    out = cmcp_artifact_summary_v1(row)

    assert out == {
        "id": 42,
        "title": "Sample Guide",
        "guide_type": "study_guide",
        # ``content_type`` is the MCP-spec alias of ``guide_type``.
        "content_type": "study_guide",
        "state": "APPROVED",
        "subject_code": "MATH",
        "grade": 5,
        "se_codes": ["MATH.5.A.1"],
        # Numeric → float coercion (no Decimal leak into JSON).
        "alignment_score": 0.876,
        "ai_engine": "openai/gpt-4o-mini",
        "course_id": 11,
        "created_at": "2026-04-29T12:00:00+00:00",
    }
    # Defensive: alignment_score is a plain float, not Decimal.
    assert isinstance(out["alignment_score"], float)


def test_cmcp_artifact_summary_v1_handles_missing_optional_attrs():
    """Non-CMCP study-guide rows + test fakes may omit the CMCP-only
    attrs (``alignment_score`` / ``ai_engine``) entirely. The projector
    must tolerate the missing attribute and surface ``None``.
    """
    minimal = SimpleNamespace(
        id=1,
        title="Plain Guide",
        guide_type="quiz",
        state="DRAFT",
        se_codes=None,
        course_id=None,
        created_at=None,
        # alignment_score + ai_engine deliberately omitted
    )
    out = cmcp_artifact_summary_v1(minimal)

    assert out["alignment_score"] is None
    assert out["ai_engine"] is None
    # ``se_codes`` is always a list, never None.
    assert out["se_codes"] == []
    # ``subject_code`` + ``grade`` derive from se_codes; both None when
    # the row carries no SE codes.
    assert out["subject_code"] is None
    assert out["grade"] is None
    # ``created_at`` None passes through to None (not "" or a 1970 ISO).
    assert out["created_at"] is None


def test_cmcp_artifact_summary_v1_prefers_real_grade_column_when_present():
    """Forward-compat: if the row exposes a real ``grade`` column (M3+),
    that value wins over the SE-code prefix parse — even if the SE code
    is well-formed and would parse to a different grade.
    """
    row = _row(grade=7, se_codes=["MATH.5.A.1"])  # real column says 7,
    # SE prefix would parse to 5 — the column should win.
    out = cmcp_artifact_summary_v1(row)
    assert out["grade"] == 7
    # subject_code still derives from the SE code prefix.
    assert out["subject_code"] == "MATH"


def test_cmcp_artifact_summary_v1_alignment_decimal_to_float():
    """Numeric / Decimal alignment_score → float so the JSON response is
    a plain number rather than a Decimal-string.
    """
    row = _row(alignment_score=Decimal("0.123"))
    out = cmcp_artifact_summary_v1(row)
    assert out["alignment_score"] == pytest.approx(0.123)
    assert isinstance(out["alignment_score"], float)


def test_cmcp_artifact_summary_v1_se_codes_always_list_copy():
    """``se_codes`` should be a fresh list on the returned dict — not a
    direct reference to the row's column. Surfaces sometimes mutate the
    response (drop fields, reorder); a shared list reference would leak
    those mutations back into the ORM row.
    """
    src = ["MATH.5.A.1", "MATH.5.A.2"]
    row = _row(se_codes=src)
    out = cmcp_artifact_summary_v1(row)
    assert out["se_codes"] == src
    assert out["se_codes"] is not src
