"""Unit tests for app/services/cmcp/embedding_alignment_validator.py — CB-CMCP-001 M3-I 3I-1 (#4658).

All OpenAI embedding calls are mocked at the
``app.services.cmcp.embedding_alignment_validator._create_embeddings``
seam — no real API calls are made.

Covers the acceptance scenarios from #4658:
1. Content matches SE → passed=True, scores all >= threshold
2. Content doesn't match → passed=False, failed_ses populated
3. Empty content → passed=False, sensible default
4. Empty se_codes → passed=False, sensible default
5. Mocked embedding service — no real API calls
"""
from __future__ import annotations

import math
from unittest.mock import patch

import pytest

from app.services.cmcp.embedding_alignment_validator import (
    DEFAULT_THRESHOLD,
    EMBEDDING_DIM,
    EmbeddingAlignmentResult,
    _cosine_similarity,
    _split_into_sections,
    validate_embedding_alignment,
)


# ---------------------------------------------------------------------------
# Per-test CEG cleanup — same pattern as test_cmcp_embed_ceg.py
# ---------------------------------------------------------------------------
#
# Note: ``app.models.curriculum`` is imported INSIDE this fixture (and the
# seed helpers below) — not at module top — because the session-scoped
# ``app`` fixture in tests/conftest.py reloads ``app.models`` after this
# test module is collected. Importing the model classes at module-top
# would bind to a stale class registry whose mapper config fails (the
# ``User`` cross-relationship gets unregistered from sys.modules).


@pytest.fixture(autouse=True)
def _wipe_ceg_tables(db_session):
    """Wipe CEG tables before each test so committed rows don't leak."""
    yield
    from app.models.curriculum import (
        CEGExpectation,
        CEGStrand,
        CEGSubject,
        CurriculumVersion,
    )
    db_session.query(CEGExpectation).delete()
    db_session.query(CEGStrand).delete()
    db_session.query(CurriculumVersion).delete()
    db_session.query(CEGSubject).delete()
    db_session.commit()


# ---------------------------------------------------------------------------
# Helpers — embedding stubs and CEG row seeding
# ---------------------------------------------------------------------------


def _unit_vector_from_axis(axis: int, dim: int = EMBEDDING_DIM) -> list[float]:
    """Build a unit vector with magnitude 1.0 on a single axis.

    Two unit vectors on different axes are orthogonal (cosine 0.0); two
    unit vectors on the same axis have cosine 1.0. This lets tests
    construct embeddings whose cosine similarity is exactly predictable
    without any floating-point noise.
    """
    v = [0.0] * dim
    v[axis % dim] = 1.0
    return v


def _mixed_vector(axis_a: int, axis_b: int, weight_a: float = 0.8) -> list[float]:
    """Build a unit-length vector that's mostly axis_a, partly axis_b.

    With ``weight_a = 0.8``, cosine similarity to ``_unit_vector_from_axis(axis_a)``
    is ``0.8 / sqrt(0.8**2 + (1-0.8)**2) ≈ 0.9701``. Useful for building
    "near-match" embeddings in tests.
    """
    weight_b = 1.0 - weight_a
    v = [0.0] * EMBEDDING_DIM
    v[axis_a % EMBEDDING_DIM] = weight_a
    v[axis_b % EMBEDDING_DIM] = weight_b
    # Normalize.
    mag = math.sqrt(sum(x * x for x in v))
    return [x / mag for x in v]


def _patch_create_embeddings(side_effect):
    """Patch ``_create_embeddings`` with a coroutine side effect."""
    return patch(
        "app.services.cmcp.embedding_alignment_validator._create_embeddings",
        side_effect=side_effect,
    )


def _seed_subject_strand_version(db_session) -> tuple[int, int, int]:
    """Create a single subject/strand/version triple. Returns ids."""
    from app.models.curriculum import CEGStrand, CEGSubject, CurriculumVersion

    subject = CEGSubject(code="MATH", name="Mathematics")
    db_session.add(subject)
    db_session.flush()
    strand = CEGStrand(subject_id=subject.id, code="B", name="Algebra")
    db_session.add(strand)
    db_session.flush()
    version = CurriculumVersion(
        subject_id=subject.id, grade=9, version="2020-rev1"
    )
    db_session.add(version)
    db_session.flush()
    db_session.commit()
    return subject.id, strand.id, version.id


def _seed_se(
    db_session,
    *,
    subject_id: int,
    strand_id: int,
    version_id: int,
    ministry_code: str,
    description: str,
    grade: int = 9,
):
    """Create a single SE row and return it."""
    from app.models.curriculum import CEGExpectation

    row = CEGExpectation(
        ministry_code=ministry_code,
        subject_id=subject_id,
        strand_id=strand_id,
        grade=grade,
        expectation_type="specific",
        description=description,
        curriculum_version_id=version_id,
        active=True,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Pure-function tests — no DB or embedding mock needed
# ---------------------------------------------------------------------------


def test_cosine_similarity_orthogonal():
    """Two orthogonal unit vectors have cosine 0.0."""
    a = _unit_vector_from_axis(0)
    b = _unit_vector_from_axis(1)
    assert _cosine_similarity(a, b) == pytest.approx(0.0)


def test_cosine_similarity_identical():
    """Two identical unit vectors have cosine 1.0."""
    a = _unit_vector_from_axis(0)
    assert _cosine_similarity(a, a) == pytest.approx(1.0)


def test_cosine_similarity_zero_vectors():
    """Zero-magnitude vectors degrade to 0.0 (not ZeroDivisionError)."""
    zero = [0.0] * EMBEDDING_DIM
    assert _cosine_similarity(zero, _unit_vector_from_axis(0)) == 0.0
    assert _cosine_similarity(_unit_vector_from_axis(0), zero) == 0.0


def test_cosine_similarity_dim_mismatch_returns_zero():
    """Mismatched-length vectors return 0.0 rather than crashing."""
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


def test_split_sections_double_hash():
    """Content with `## ` headings splits into one section per heading."""
    content = "## Section A\nbody A\n\n## Section B\nbody B"
    sections = _split_into_sections(content)
    assert len(sections) == 2
    assert sections[0].startswith("## Section A")
    assert "body A" in sections[0]
    assert sections[1].startswith("## Section B")
    assert "body B" in sections[1]


def test_split_sections_single_hash_fallback():
    """No `##` headings falls back to splitting on `# ` headings."""
    content = "# Top A\nbody A\n\n# Top B\nbody B"
    sections = _split_into_sections(content)
    assert len(sections) == 2
    assert sections[0].startswith("# Top A")


def test_split_sections_no_headings_returns_whole_content():
    """Content without any markdown headings is returned as a single section."""
    content = "Just a plain paragraph with no headings."
    sections = _split_into_sections(content)
    assert sections == [content]


def test_split_sections_empty_returns_empty_list():
    """Empty / whitespace-only content returns []."""
    assert _split_into_sections("") == []
    assert _split_into_sections("   \n  \t  ") == []


def test_split_sections_drops_blank_sections():
    """Blank sections (only whitespace between headings) are dropped."""
    content = "## A\nbody\n\n## \n\n## C\nbody C"
    sections = _split_into_sections(content)
    # Each section is the heading + body; blank-heading section may
    # survive as `## ` text — confirm we never end up with whitespace-only.
    for s in sections:
        assert s.strip() != ""


# ---------------------------------------------------------------------------
# Scenario 1 — Content matches SE → passed=True
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_content_matches_all_ses_passes(db_session):
    """When every SE's embedding aligns with a content section, passed=True."""
    subject_id, strand_id, version_id = _seed_subject_strand_version(db_session)
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.3",
        description="Solve quadratic equations by factoring.",
    )
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.4",
        description="Graph parabolas using vertex form.",
    )

    content = "## Quadratics\nbody\n\n## Parabolas\nbody"

    # Build embeddings so:
    #   sections[0] (Quadratics) ≈ axis 0
    #   sections[1] (Parabolas)  ≈ axis 1
    # SE B2.3 (factoring) ≈ axis 0  → cosine(s0, se0)=1.0
    # SE B2.4 (parabolas) ≈ axis 1  → cosine(s1, se1)=1.0
    section_embs = [_unit_vector_from_axis(0), _unit_vector_from_axis(1)]
    se_embs_in_db_order = {
        "B2.3": _unit_vector_from_axis(0),
        "B2.4": _unit_vector_from_axis(1),
    }

    async def fake_create_embeddings(texts):
        # Order matches validate_embedding_alignment's batching: sections
        # first, then SE descriptions in the order they were resolved.
        out = list(section_embs)
        # Resolved SE order = input se_codes order, preserved by the
        # validator. SE descriptions follow.
        # The SE description text uniquely identifies which SE we're
        # embedding — match by description content.
        for text in texts[len(section_embs):]:
            if "factoring" in text:
                out.append(se_embs_in_db_order["B2.3"])
            elif "parabolas" in text or "vertex" in text:
                out.append(se_embs_in_db_order["B2.4"])
            else:
                out.append([0.0] * EMBEDDING_DIM)
        return out

    with _patch_create_embeddings(fake_create_embeddings):
        result = await validate_embedding_alignment(
            content=content,
            se_codes=["B2.3", "B2.4"],
            db=db_session,
            threshold=DEFAULT_THRESHOLD,
        )

    assert result["passed"] is True
    assert result["failed_ses"] == []
    assert result["threshold"] == DEFAULT_THRESHOLD
    # Both SEs scored at the maximum (1.0).
    assert result["scores"]["B2.3"] == pytest.approx(1.0)
    assert result["scores"]["B2.4"] == pytest.approx(1.0)
    assert result["error"] is None


@pytest.mark.asyncio
async def test_passed_true_validates_against_pydantic_model(db_session):
    """Returned dict round-trips through EmbeddingAlignmentResult."""
    subject_id, strand_id, version_id = _seed_subject_strand_version(db_session)
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.3",
        description="Solve quadratics.",
    )

    async def fake(texts):
        return [_unit_vector_from_axis(0)] * len(texts)

    with _patch_create_embeddings(fake):
        result = await validate_embedding_alignment(
            content="## Quadratics\nbody",
            se_codes=["B2.3"],
            db=db_session,
        )

    parsed = EmbeddingAlignmentResult(**result)
    assert parsed.passed is True
    assert parsed.failed_ses == []


# ---------------------------------------------------------------------------
# Scenario 2 — Content doesn't match → passed=False, failed_ses populated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_content_does_not_match_fails(db_session):
    """When content is orthogonal to every SE, passed=False with all SEs failed."""
    subject_id, strand_id, version_id = _seed_subject_strand_version(db_session)
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.3",
        description="Solve quadratics by factoring.",
    )
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.4",
        description="Graph parabolas in vertex form.",
    )

    content = "## Off-topic\nThis is about geography, not math at all."

    async def fake(texts):
        # Single section on axis 0; both SEs on axis 5 → cosine 0.0
        return [
            _unit_vector_from_axis(0),  # one section
            _unit_vector_from_axis(5),  # SE B2.3
            _unit_vector_from_axis(5),  # SE B2.4
        ]

    with _patch_create_embeddings(fake):
        result = await validate_embedding_alignment(
            content=content,
            se_codes=["B2.3", "B2.4"],
            db=db_session,
            threshold=DEFAULT_THRESHOLD,
        )

    assert result["passed"] is False
    assert sorted(result["failed_ses"]) == ["B2.3", "B2.4"]
    assert result["scores"]["B2.3"] == pytest.approx(0.0)
    assert result["scores"]["B2.4"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_partial_match_only_failing_ses_in_list(db_session):
    """When SOME SEs pass and others fail, only failures appear in failed_ses."""
    subject_id, strand_id, version_id = _seed_subject_strand_version(db_session)
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.3",
        description="Solve quadratics.",
    )
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.4",
        description="Graph parabolas.",
    )

    content = "## Quadratics\nbody"

    async def fake(texts):
        return [
            _unit_vector_from_axis(0),  # section
            _unit_vector_from_axis(0),  # SE B2.3 → cosine 1.0 with section
            _unit_vector_from_axis(5),  # SE B2.4 → cosine 0.0 with section
        ]

    with _patch_create_embeddings(fake):
        result = await validate_embedding_alignment(
            content=content,
            se_codes=["B2.3", "B2.4"],
            db=db_session,
            threshold=DEFAULT_THRESHOLD,
        )

    assert result["passed"] is False
    assert result["failed_ses"] == ["B2.4"]
    assert result["scores"]["B2.3"] == pytest.approx(1.0)
    assert result["scores"]["B2.4"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_max_similarity_across_sections(db_session):
    """An SE's score is the MAX similarity across all content sections."""
    subject_id, strand_id, version_id = _seed_subject_strand_version(db_session)
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.3",
        description="Quadratics.",
    )

    content = "## A\nbody A\n\n## B\nbody B"

    async def fake(texts):
        # Section 0 orthogonal; section 1 identical to SE → max sim 1.0
        return [
            _unit_vector_from_axis(5),  # section A
            _unit_vector_from_axis(0),  # section B
            _unit_vector_from_axis(0),  # SE B2.3
        ]

    with _patch_create_embeddings(fake):
        result = await validate_embedding_alignment(
            content=content,
            se_codes=["B2.3"],
            db=db_session,
            threshold=DEFAULT_THRESHOLD,
        )

    assert result["passed"] is True
    assert result["scores"]["B2.3"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Scenario 3 — Empty content → passed=False
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_content_fails(db_session):
    """Empty string content returns passed=False, all SEs in failed_ses."""
    # No need to seed — short-circuits before DB lookup.
    result = await validate_embedding_alignment(
        content="",
        se_codes=["B2.3", "B2.4"],
        db=db_session,
    )
    assert result["passed"] is False
    assert sorted(result["failed_ses"]) == ["B2.3", "B2.4"]
    assert result["error"] == "empty content"
    assert result["scores"] == {"B2.3": 0.0, "B2.4": 0.0}


@pytest.mark.asyncio
async def test_whitespace_only_content_fails(db_session):
    """Whitespace-only content also fails with empty-content error."""
    result = await validate_embedding_alignment(
        content="   \n\n \t  ",
        se_codes=["B2.3"],
        db=db_session,
    )
    assert result["passed"] is False
    assert result["failed_ses"] == ["B2.3"]
    assert result["error"] == "empty content"


# ---------------------------------------------------------------------------
# Scenario 4 — Empty se_codes → passed=False, sensible default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_se_codes_fails(db_session):
    """Empty se_codes list returns passed=False with no failed_ses."""
    result = await validate_embedding_alignment(
        content="## Some content\nbody",
        se_codes=[],
        db=db_session,
    )
    assert result["passed"] is False
    assert result["failed_ses"] == []
    assert result["scores"] == {}
    assert result["error"] == "no se_codes provided"


# ---------------------------------------------------------------------------
# Scenario 5 — Mocked embedding service (no real API calls)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_embedding_api_failure_handled_gracefully(db_session):
    """If the embedding API raises, validator returns failed result, no exception."""
    subject_id, strand_id, version_id = _seed_subject_strand_version(db_session)
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.3",
        description="Quadratics.",
    )

    async def fake(_texts):
        raise RuntimeError("OpenAI rate-limited")

    with _patch_create_embeddings(fake):
        result = await validate_embedding_alignment(
            content="## A\nbody",
            se_codes=["B2.3"],
            db=db_session,
        )

    assert result["passed"] is False
    assert result["failed_ses"] == ["B2.3"]
    assert result["error"] is not None
    assert "embedding_error" in result["error"]
    assert "OpenAI rate-limited" in result["error"]


@pytest.mark.asyncio
async def test_embedding_count_mismatch_handled(db_session):
    """If the mock returns wrong number of embeddings, validator fails gracefully."""
    subject_id, strand_id, version_id = _seed_subject_strand_version(db_session)
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.3",
        description="Quadratics.",
    )

    async def fake(_texts):
        # Should return 2 (1 section + 1 SE) but returns 1.
        return [_unit_vector_from_axis(0)]

    with _patch_create_embeddings(fake):
        result = await validate_embedding_alignment(
            content="## A\nbody",
            se_codes=["B2.3"],
            db=db_session,
        )

    assert result["passed"] is False
    assert result["error"] is not None
    assert "embedding_count_mismatch" in result["error"]


# ---------------------------------------------------------------------------
# Additional — unresolved SE codes, threshold knob, case-insensitive lookup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unresolved_se_codes_surface_error(db_session):
    """SE codes not in the DB get score 0.0, fail, and produce error."""
    subject_id, strand_id, version_id = _seed_subject_strand_version(db_session)
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.3",
        description="Quadratics.",
    )
    # Note: B9.9 NOT seeded → unresolved.

    async def fake(texts):
        return [_unit_vector_from_axis(0)] * len(texts)

    with _patch_create_embeddings(fake):
        result = await validate_embedding_alignment(
            content="## A\nbody",
            se_codes=["B2.3", "B9.9"],
            db=db_session,
        )

    assert result["passed"] is False
    assert "B9.9" in result["failed_ses"]
    assert result["scores"]["B9.9"] == 0.0
    # B2.3 was matched perfectly.
    assert result["scores"]["B2.3"] == pytest.approx(1.0)
    assert result["error"] is not None
    assert "unresolved_se_codes" in result["error"]


@pytest.mark.asyncio
async def test_no_se_codes_resolve_short_circuits_embedding(db_session):
    """When ALL SE codes are unresolved, no embedding API call is made."""
    # No CEG rows seeded.
    call_count = {"n": 0}

    async def fake(_texts):
        call_count["n"] += 1
        return []

    with _patch_create_embeddings(fake):
        result = await validate_embedding_alignment(
            content="## A\nbody",
            se_codes=["UNKNOWN.1", "UNKNOWN.2"],
            db=db_session,
        )

    assert call_count["n"] == 0  # short-circuit verified
    assert result["passed"] is False
    assert sorted(result["failed_ses"]) == ["UNKNOWN.1", "UNKNOWN.2"]
    assert result["error"] is not None
    assert "no SE descriptions resolved" in result["error"]


@pytest.mark.asyncio
async def test_custom_threshold_changes_pass_fail_outcome(db_session):
    """Threshold knob affects which SEs are considered failed."""
    subject_id, strand_id, version_id = _seed_subject_strand_version(db_session)
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.3",
        description="Quadratics.",
    )

    # Build a section/SE pair with cosine ~0.97 (mostly axis 0, partly axis 1).
    section_emb = _mixed_vector(0, 1, weight_a=0.8)

    async def fake(_texts):
        return [
            section_emb,  # section
            _unit_vector_from_axis(0),  # SE B2.3 → cosine ≈ 0.97
        ]

    # With default threshold 0.65, passes.
    with _patch_create_embeddings(fake):
        result_default = await validate_embedding_alignment(
            content="## A\nbody",
            se_codes=["B2.3"],
            db=db_session,
            threshold=0.65,
        )
    assert result_default["passed"] is True

    # With threshold 0.99, fails (0.97 < 0.99).
    with _patch_create_embeddings(fake):
        result_strict = await validate_embedding_alignment(
            content="## A\nbody",
            se_codes=["B2.3"],
            db=db_session,
            threshold=0.99,
        )
    assert result_strict["passed"] is False
    assert result_strict["failed_ses"] == ["B2.3"]


@pytest.mark.asyncio
async def test_se_code_lookup_is_case_insensitive(db_session):
    """SE codes match case-insensitively against ministry_code."""
    subject_id, strand_id, version_id = _seed_subject_strand_version(db_session)
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.3",  # canonical uppercase
        description="Quadratics.",
    )

    async def fake(_texts):
        return [_unit_vector_from_axis(0)] * 2

    # Input as lowercase — must still resolve.
    with _patch_create_embeddings(fake):
        result = await validate_embedding_alignment(
            content="## A\nbody",
            se_codes=["b2.3"],
            db=db_session,
        )

    assert result["passed"] is True
    # Score key uses input casing.
    assert result["scores"]["b2.3"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_mock_seam_is_not_real_openai(db_session, monkeypatch):
    """Smoke check: validator never reaches the real OpenAI client when mocked."""
    subject_id, strand_id, version_id = _seed_subject_strand_version(db_session)
    _seed_se(
        db_session,
        subject_id=subject_id, strand_id=strand_id, version_id=version_id,
        ministry_code="B2.3",
        description="Quadratics.",
    )

    # Sabotage: if any code path reaches the real openai SDK we'd want to know.
    # The mock seam makes this impossible, but we double-check by patching
    # the openai module itself to raise on import access.
    import sys

    real_openai = sys.modules.get("openai")

    class _ExplodingOpenAI:
        def __getattr__(self, name):
            raise AssertionError(
                f"validator reached real openai.{name} despite mock"
            )

    sys.modules["openai"] = _ExplodingOpenAI()
    try:
        async def fake(texts):
            return [_unit_vector_from_axis(0)] * len(texts)

        with _patch_create_embeddings(fake):
            result = await validate_embedding_alignment(
                content="## A\nbody",
                se_codes=["B2.3"],
                db=db_session,
            )

        assert result["passed"] is True
    finally:
        if real_openai is not None:
            sys.modules["openai"] = real_openai
        else:
            sys.modules.pop("openai", None)
