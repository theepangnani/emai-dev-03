"""Tests for CB-CMCP-001 M3-E 3E-2 (#4654) — coverage map service.

Covers
------
- Computes correct strand × grade counts for a seeded board.
- APPROVED-only — DRAFT / SELF_STUDY / PENDING_REVIEW / REJECTED are
  excluded from the count.
- ``archived_at IS NOT NULL`` rows are excluded.
- Empty board (no APPROVED rows) → ``{}`` (NOT an error).
- Cross-board isolation — board X's map doesn't include board Y's rows.
- ``board_id IS NULL`` rows are excluded (deny-on-NULL pattern).
- Malformed SE codes are skipped (don't crash aggregation).
- ``board_id`` accepted as both ``int`` and ``str`` (3E-1 REST path
  shape vs. resolved User.board_id string).
- ``board_id=None`` guard returns empty (no cross-board leak).

Pure service — no routes, no auth — so we exercise it directly with the
shared ``db_session`` fixture and seed rows via the ORM. Per the file
header, we don't need real Claude / OpenAI calls; the coverage service
itself touches no external APIs.
"""
from __future__ import annotations

from uuid import uuid4

import pytest


# ── User + StudyGuide seed helpers ─────────────────────────────────────

def _make_user(db_session):
    """Create a minimal user owning the seeded study_guides rows.

    The coverage service doesn't filter by user, but ``StudyGuide`` has
    a non-null ``user_id`` FK — we need *some* User row to satisfy the
    constraint. Role doesn't matter; default to ADMIN for brevity.
    """
    from app.core.security import get_password_hash
    from app.models.user import User, UserRole

    user = User(
        email=f"covmap_{uuid4().hex[:8]}@test.com",
        full_name="Coverage Map Test User",
        role=UserRole.ADMIN,
        hashed_password=get_password_hash("Password123!"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _seed_artifact(
    db_session,
    *,
    user_id: int,
    state: str = "APPROVED",
    se_codes: list[str] | None = None,
    board_id: str | None = "TDSB",
    archived: bool = False,
):
    """Insert one ``study_guides`` row with the given coverage shape."""
    from datetime import datetime, timezone

    from app.models.study_guide import StudyGuide

    row = StudyGuide(
        user_id=user_id,
        title=f"covmap-{uuid4().hex[:6]}",
        content="body",
        guide_type="study_guide",
        state=state,
        se_codes=se_codes,
        board_id=board_id,
        archived_at=(
            datetime.now(tz=timezone.utc) if archived else None
        ),
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.fixture()
def covmap_user(db_session):
    """One owner User for all seeded rows in a test."""
    return _make_user(db_session)


@pytest.fixture()
def cleanup_artifacts(db_session):
    """Remove any ``study_guides`` rows from before AND after each test.

    The session-scoped DB fixture in ``conftest.py`` keeps rows across
    tests, so other CMCP test files that seed board="TDSB" artifacts
    (board_catalog, board_signed_csv, version_cascade, etc.) leave
    rows that pollute coverage-map counts. Clean BEFORE the test runs
    so this file's count assertions only see this test's seeded rows,
    and AFTER so we don't pollute downstream tests.
    """
    from app.models.study_guide import StudyGuide

    db_session.query(StudyGuide).delete(synchronize_session=False)
    db_session.commit()
    yield
    db_session.query(StudyGuide).delete(synchronize_session=False)
    db_session.commit()


# ── Tests ──────────────────────────────────────────────────────────────


def test_computes_correct_counts_for_seeded_board(
    db_session, covmap_user, cleanup_artifacts
):
    """Two strands, two grades each, with varying counts → correct pivot."""
    from app.services.cmcp.coverage_map_service import compute_coverage_map

    # Strand A grade 5: 2 rows.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.A.1"],
        board_id="TDSB",
    )
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.A.2"],
        board_id="TDSB",
    )
    # Strand A grade 6: 1 row.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.6.A.1"],
        board_id="TDSB",
    )
    # Strand B grade 5: 3 rows.
    for tail in ("1", "2", "3"):
        _seed_artifact(
            db_session,
            user_id=covmap_user.id,
            se_codes=[f"MATH.5.B.{tail}"],
            board_id="TDSB",
        )

    result = compute_coverage_map("TDSB", db_session)

    assert result == {
        "A": {5: 2, 6: 1},
        "B": {5: 3},
    }


def test_only_approved_rows_are_counted(
    db_session, covmap_user, cleanup_artifacts
):
    """DRAFT / SELF_STUDY / PENDING_REVIEW / REJECTED rows are excluded."""
    from app.services.cmcp.coverage_map_service import compute_coverage_map

    # One APPROVED row that should appear.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        state="APPROVED",
        se_codes=["MATH.5.A.1"],
        board_id="TDSB",
    )
    # Non-APPROVED rows that should NOT appear.
    for state in ("DRAFT", "SELF_STUDY", "PENDING_REVIEW", "REJECTED"):
        _seed_artifact(
            db_session,
            user_id=covmap_user.id,
            state=state,
            se_codes=["MATH.5.A.1"],
            board_id="TDSB",
        )

    result = compute_coverage_map("TDSB", db_session)

    assert result == {"A": {5: 1}}


def test_archived_rows_are_excluded(
    db_session, covmap_user, cleanup_artifacts
):
    """Soft-deleted (``archived_at`` set) rows don't count."""
    from app.services.cmcp.coverage_map_service import compute_coverage_map

    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.A.1"],
        board_id="TDSB",
        archived=False,
    )
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.A.1"],
        board_id="TDSB",
        archived=True,
    )

    result = compute_coverage_map("TDSB", db_session)

    assert result == {"A": {5: 1}}


def test_empty_strands_returns_empty_dict(
    db_session, covmap_user, cleanup_artifacts
):
    """Board with no APPROVED rows → ``{}`` (NOT an error)."""
    from app.services.cmcp.coverage_map_service import compute_coverage_map

    # Seed only non-APPROVED rows so the board exists but has no
    # coverage to count.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        state="DRAFT",
        se_codes=["MATH.5.A.1"],
        board_id="TDSB",
    )

    result = compute_coverage_map("TDSB", db_session)

    assert result == {}


def test_completely_empty_board_returns_empty_dict(
    db_session, covmap_user, cleanup_artifacts
):
    """Unknown board_id with no rows → ``{}`` (NOT an error)."""
    from app.services.cmcp.coverage_map_service import compute_coverage_map

    result = compute_coverage_map("BOARD_THAT_DOES_NOT_EXIST", db_session)

    assert result == {}


def test_cross_board_isolation(
    db_session, covmap_user, cleanup_artifacts
):
    """Board X's map doesn't include board Y's artifacts."""
    from app.services.cmcp.coverage_map_service import compute_coverage_map

    # Board TDSB rows.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.A.1"],
        board_id="TDSB",
    )
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.A.2"],
        board_id="TDSB",
    )
    # Board PDSB row (different board).
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.B.1"],
        board_id="PDSB",
    )
    # Board YRDSB row (different board).
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.6.C.1"],
        board_id="YRDSB",
    )

    tdsb_map = compute_coverage_map("TDSB", db_session)
    pdsb_map = compute_coverage_map("PDSB", db_session)
    yrdsb_map = compute_coverage_map("YRDSB", db_session)

    assert tdsb_map == {"A": {5: 2}}
    assert pdsb_map == {"B": {5: 1}}
    assert yrdsb_map == {"C": {6: 1}}


def test_board_id_null_rows_are_excluded(
    db_session, covmap_user, cleanup_artifacts
):
    """Rows with ``board_id IS NULL`` don't appear in any board's map.

    Mirrors the deny-on-NULL pattern used by the visibility helper —
    legacy / non-board-stamped rows are NOT visible to a board admin's
    coverage view.
    """
    from app.services.cmcp.coverage_map_service import compute_coverage_map

    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.A.1"],
        board_id="TDSB",
    )
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.B.1"],
        board_id=None,
    )

    tdsb_map = compute_coverage_map("TDSB", db_session)

    assert tdsb_map == {"A": {5: 1}}
    assert "B" not in tdsb_map


def test_malformed_se_codes_are_skipped(
    db_session, covmap_user, cleanup_artifacts
):
    """Rows with broken SE code shapes are skipped, not crashed on."""
    from app.services.cmcp.coverage_map_service import compute_coverage_map

    # Valid row.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.A.1"],
        board_id="TDSB",
    )
    # Empty list.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=[],
        board_id="TDSB",
    )
    # NULL.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=None,
        board_id="TDSB",
    )
    # Too few segments.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5"],
        board_id="TDSB",
    )
    # Non-int grade segment.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.X.A.1"],
        board_id="TDSB",
    )
    # Non-string first entry.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=[12345],
        board_id="TDSB",
    )
    # Empty strand segment.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5..1"],
        board_id="TDSB",
    )

    result = compute_coverage_map("TDSB", db_session)

    # Only the one valid row counts.
    assert result == {"A": {5: 1}}


def test_board_id_accepts_int_and_str(
    db_session, covmap_user, cleanup_artifacts
):
    """``compute_coverage_map`` accepts both ``int`` and ``str`` board ids.

    3E-1 (board catalog REST endpoint) takes ``board_id`` from a path
    param typed as ``int``; a board admin User row carries the id as a
    string. Both paths must reach the same coverage map. The service
    coerces to ``str`` for the SQL filter.
    """
    from app.services.cmcp.coverage_map_service import compute_coverage_map

    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.A.1"],
        board_id="42",
    )

    str_result = compute_coverage_map("42", db_session)
    int_result = compute_coverage_map(42, db_session)

    assert str_result == int_result == {"A": {5: 1}}


def test_board_id_none_returns_empty(
    db_session, covmap_user, cleanup_artifacts
):
    """``board_id=None`` short-circuits to empty (no cross-board leak)."""
    from app.services.cmcp.coverage_map_service import compute_coverage_map

    # Seed a row with NULL board_id — even if the guard were missing,
    # this would be the only row that could match.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.A.1"],
        board_id=None,
    )
    # And one with a real board_id, for good measure.
    _seed_artifact(
        db_session,
        user_id=covmap_user.id,
        se_codes=["MATH.5.B.1"],
        board_id="TDSB",
    )

    result = compute_coverage_map(None, db_session)  # type: ignore[arg-type]

    assert result == {}
