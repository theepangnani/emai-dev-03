"""Ontario Curriculum Management REST API (CB-CMCP-001 M0-B 0B-1, #4415).

Direct port of phase-2's ``app/api/routes/curriculum.py`` adapted to the
dev-03 feature-flag system. Three read-only endpoints expose seeded
Ontario curriculum expectations to the prompt builder and (eventually)
the board surface (per locked decision D7=B):

    GET /api/curriculum/courses                  — list seeded course codes
    GET /api/curriculum/{course_code}            — expectations grouped by strand
    GET /api/curriculum/{course_code}/search?q=  — keyword search within a course

Cross-stripe dependency
-----------------------
The SQLAlchemy model ``CEGExpectation`` (a.k.a. ``CurriculumExpectation``)
is owned by stripe **0A-1**. To keep this PR independently testable
before 0A-1 lands on the integration branch, the model import lives
behind a ``try/except ImportError`` guard — if the model is absent the
routes return 503 (feature unavailable) so callers see a clean failure
mode instead of an opaque AttributeError.

Feature flag
------------
Gated by ``cmcp.enabled`` (default OFF). Other CB-CMCP-001 stripes will
reuse the same flag. When the flag is OFF every endpoint returns 403
*before* any DB work, mirroring the DCI gating pattern.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.services.feature_flag_service import is_feature_enabled

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/curriculum", tags=["Ontario Curriculum"])


# ---------------------------------------------------------------------------
# Feature-flag constants
# ---------------------------------------------------------------------------

CMCP_FEATURE_FLAG_KEY = "cmcp.enabled"


def require_cmcp_enabled(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Dependency: 401 if unauthed, 403 if ``cmcp.enabled`` is OFF.

    Authentication is resolved first via ``get_current_user``, so an
    unauth request always sees 401 even when CB-CMCP-001 is disabled —
    flag-state probing without a valid token is not possible.
    """
    if not is_feature_enabled(CMCP_FEATURE_FLAG_KEY, db=db):
        raise HTTPException(status_code=403, detail="CB-CMCP-001 is not enabled")
    return current_user


# ---------------------------------------------------------------------------
# Forward-declared model import (Option A from #4415)
# ---------------------------------------------------------------------------
#
# Stripe 0A-1 will land ``app/models/curriculum.py`` with the canonical
# ``CEGExpectation`` SQLAlchemy model. Until that ships we keep this
# stripe importable + testable by guarding the import. When the model is
# absent every endpoint returns 503 — chosen over a hard import error so
# the rest of the app keeps booting in CI.
#
# When 0A-1 merges, this stripe rebases cleanly: the import succeeds and
# the routes start serving live data with no further code changes.

if TYPE_CHECKING:  # pragma: no cover — typing only
    from app.models.curriculum import CurriculumExpectation as _ExpectationModel

_EXPECTATION_MODEL = None  # type: Optional[type]
try:  # pragma: no cover — exercised in integration once 0A-1 lands
    from app.models.curriculum import CurriculumExpectation as _LiveExpectationModel
    _EXPECTATION_MODEL = _LiveExpectationModel
except ImportError:
    logger.info(
        "CB-CMCP-001: app.models.curriculum.CurriculumExpectation not present "
        "(stripe 0A-1 not merged yet) — endpoints will return 503 until model lands"
    )


def _require_model() -> type:
    """Return the live ``CurriculumExpectation`` model or raise 503.

    Centralizing the check keeps the handlers readable: they can assume
    the model exists once this returns.
    """
    if _EXPECTATION_MODEL is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Curriculum data model is not available "
                "(CB-CMCP-001 stripe 0A-1 must merge before this endpoint serves)"
            ),
        )
    return _EXPECTATION_MODEL


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------


class ExpectationItem(BaseModel):
    code: str
    description: str
    type: str

    model_config = {"from_attributes": True}


class StrandGroup(BaseModel):
    name: str
    expectations: list[ExpectationItem]


class CurriculumCourseResponse(BaseModel):
    course_code: str
    grade_level: int
    strands: list[StrandGroup]


class CourseListItem(BaseModel):
    course_code: str
    grade_level: int
    expectation_count: int


# ---------------------------------------------------------------------------
# GET /api/curriculum/courses
# ---------------------------------------------------------------------------


@router.get("/courses", response_model=list[CourseListItem])
def list_curriculum_courses(
    _user: User = Depends(require_cmcp_enabled),
    db: Session = Depends(get_db),
):
    """Return all course codes that have seeded curriculum expectations."""
    # Aggregate in a single query so we don't issue O(N) COUNT subqueries
    # over the course list. Phase-2 used `distinct(model.course_code)`
    # which is PG-specific (DISTINCT ON) and silently no-ops on SQLite —
    # surfaced as a SQLAlchemy deprecation warning in tests. Replacing
    # it with GROUP BY + COUNT keeps cross-DB parity (PG + SQLite) and
    # collapses the N+1 to a single round-trip.
    model = _require_model()
    rows = (
        db.query(
            model.course_code,
            func.max(model.grade_level).label("grade_level"),
            func.count(model.id).label("expectation_count"),
        )
        .group_by(model.course_code)
        .order_by(model.course_code)
        .all()
    )
    return [
        CourseListItem(
            course_code=row.course_code,
            grade_level=row.grade_level,
            expectation_count=row.expectation_count,
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# GET /api/curriculum/{course_code}
# ---------------------------------------------------------------------------


def _load_course_expectations(db: Session, course_code: str):
    """Fetch ordered expectation rows for a course, raising 404 if empty."""
    model = _require_model()
    course_code = course_code.upper()
    expectations = (
        db.query(model)
        .filter(model.course_code == course_code)
        .order_by(model.strand, model.expectation_code)
        .all()
    )
    if not expectations:
        raise HTTPException(
            status_code=404,
            detail=f"No curriculum data found for course {course_code}",
        )
    return course_code, expectations


def _group_by_strand(expectations) -> list[StrandGroup]:
    """Group an ordered list of expectation rows into ``StrandGroup`` records."""
    strands: dict[str, list[ExpectationItem]] = {}
    for exp in expectations:
        if exp.strand not in strands:
            strands[exp.strand] = []
        strands[exp.strand].append(ExpectationItem(
            code=exp.expectation_code,
            description=exp.description,
            type=exp.expectation_type,
        ))
    return [
        StrandGroup(name=name, expectations=items)
        for name, items in strands.items()
    ]


def _build_course_response(db: Session, course_code: str) -> CurriculumCourseResponse:
    """Shared core for ``GET /{course_code}`` and the empty-query fallback in
    ``GET /{course_code}/search``. Kept as a plain helper so the search
    route can reuse it without re-triggering FastAPI dependency
    injection (calling a ``@router.get``-decorated function directly
    would still work but is brittle and confusing).
    """
    course_code, expectations = _load_course_expectations(db, course_code)
    grade_level = expectations[0].grade_level
    return CurriculumCourseResponse(
        course_code=course_code,
        grade_level=grade_level,
        strands=_group_by_strand(expectations),
    )


@router.get("/{course_code}", response_model=CurriculumCourseResponse)
def get_curriculum_for_course(
    course_code: str,
    _user: User = Depends(require_cmcp_enabled),
    db: Session = Depends(get_db),
):
    """Return all expectations for a course, grouped by strand.

    Returns ``{ course_code, grade_level, strands: [{ name, expectations: [{code, description, type}] }] }``.
    """
    return _build_course_response(db, course_code)


# ---------------------------------------------------------------------------
# GET /api/curriculum/{course_code}/search
# ---------------------------------------------------------------------------


@router.get("/{course_code}/search", response_model=CurriculumCourseResponse)
def search_curriculum_expectations(
    course_code: str,
    q: Optional[str] = Query(None, min_length=1, max_length=200),
    _user: User = Depends(require_cmcp_enabled),
    db: Session = Depends(get_db),
):
    """Search expectations for a course by keyword (case-insensitive substring match).

    Returns the same grouped structure as ``GET /{course_code}``, but
    only including expectations whose description **or** expectation
    code contains the query string. An empty / missing ``q`` falls
    through to the un-filtered course view. A query that matches no
    expectations returns the course shell with an empty ``strands``
    list — *not* a 404 — so the UI can render a "no matches" state.
    """
    model = _require_model()
    course_code = course_code.upper()

    if not q or not q.strip():
        return _build_course_response(db, course_code)

    q_lower = q.strip().lower()

    expectations = (
        db.query(model)
        .filter(
            model.course_code == course_code,
            or_(
                model.description.ilike(f"%{q_lower}%"),
                model.expectation_code.ilike(f"%{q_lower}%"),
            ),
        )
        .order_by(model.strand, model.expectation_code)
        .all()
    )

    if not expectations:
        # Empty result on a known course — return the shell with empty
        # strands. 404 only when the course itself has no seeded data.
        all_exp = (
            db.query(model)
            .filter(model.course_code == course_code)
            .first()
        )
        if not all_exp:
            raise HTTPException(
                status_code=404,
                detail=f"No curriculum data found for course {course_code}",
            )
        return CurriculumCourseResponse(
            course_code=course_code,
            grade_level=all_exp.grade_level,
            strands=[],
        )

    grade_level = expectations[0].grade_level
    return CurriculumCourseResponse(
        course_code=course_code,
        grade_level=grade_level,
        strands=_group_by_strand(expectations),
    )
