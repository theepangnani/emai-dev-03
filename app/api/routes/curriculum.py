"""Ontario Curriculum Management REST API (CB-CMCP-001 M0-B 0B-1, #4415).

Three read-only endpoints expose the seeded Ontario curriculum graph
(per locked decision D7=B) to the prompt builder and (eventually) the
board surface:

    GET /api/curriculum/courses                  — list seeded subject codes
    GET /api/curriculum/{course_code}            — expectations grouped by strand
    GET /api/curriculum/{course_code}/search?q=  — keyword search within a course

Schema bridge (#4426)
---------------------
The original 0B-1 port targeted the phase-2 flat ``CurriculumExpectation``
model (single table with ``course_code`` + ``strand`` strings). That
model never landed in dev-03; stripe 0A-1 (#4425) shipped the new
normalized CEG schema instead:

    CEGSubject ── 1:N ── CEGStrand ── 1:N ── CEGExpectation

This module now queries the normalized schema directly. The forward-
declared try/except import guard + 503 fallback are gone — ``CEGExpectation``
is a hard import like any other model.

API contract / mapping decision
-------------------------------
The phase-2 ``course_code`` was an Ontario course code (e.g., "MTH1W")
that encoded subject + grade + stream into one identifier. The new CEG
schema separates ``CEGSubject.code`` (e.g., "MATH") from
``CEGExpectation.grade``. To minimize URL-contract churn and preserve
the response shape, we map:

    course_code  ← CEGSubject.code      (e.g., "MATH", "LANG")
    grade_level  ← max(CEGExpectation.grade) per subject

Rationale: the issue (#4426) explicitly suggests this mapping. The
multi-grade subjects (e.g., MATH covers G1-G8) report the highest grade
seeded; this is deterministic and aligned with the data invariant the
seed pipeline assumes (one active subject row per code). Future stripes
that need finer-grained "course" semantics (e.g., MTH1W vs MPM2D) can
extend the URL to ``/courses/{subject}/{grade}`` without breaking
existing callers.

Feature flag
------------
Gated by ``cmcp.enabled`` (default OFF). Other CB-CMCP-001 stripes
reuse the same flag. When the flag is OFF every endpoint returns 403
*before* any DB work, mirroring the DCI gating pattern.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.curriculum import CEGExpectation, CEGStrand, CEGSubject
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
    """Return all subject codes that have seeded curriculum expectations.

    One row per ``CEGSubject`` that has at least one expectation. The
    aggregation runs in a single query — JOIN ``CEGExpectation`` to
    ``CEGSubject`` then GROUP BY subject code — so the round-trip count
    is O(1) regardless of subject count.
    """
    rows = (
        db.query(
            CEGSubject.code.label("course_code"),
            func.max(CEGExpectation.grade).label("grade_level"),
            func.count(CEGExpectation.id).label("expectation_count"),
        )
        .join(CEGExpectation, CEGExpectation.subject_id == CEGSubject.id)
        .filter(
            CEGExpectation.active.is_(True),
            CEGExpectation.review_state == "accepted",
        )
        .group_by(CEGSubject.code)
        .order_by(CEGSubject.code)
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
    """Fetch ordered ``(expectation, strand_name, grade)`` tuples for a
    subject code, raising 404 if no rows exist.

    Returns a tuple ``(course_code, rows)`` where ``rows`` is a list of
    ``(CEGExpectation, strand_name, grade)`` triples ordered by strand
    code then ministry code — matches the phase-2 ``ORDER BY strand,
    expectation_code`` semantics under the new schema.
    """
    course_code = course_code.upper()
    rows = (
        db.query(
            CEGExpectation,
            CEGStrand.name.label("strand_name"),
        )
        .join(CEGStrand, CEGExpectation.strand_id == CEGStrand.id)
        .join(CEGSubject, CEGExpectation.subject_id == CEGSubject.id)
        .filter(
            func.upper(CEGSubject.code) == course_code,
            CEGExpectation.active.is_(True),
            CEGExpectation.review_state == "accepted",
        )
        .order_by(CEGStrand.code, CEGExpectation.ministry_code)
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No curriculum data found for course {course_code}",
        )
    return course_code, rows


def _group_by_strand(rows) -> list[StrandGroup]:
    """Group an ordered list of ``(expectation, strand_name)`` rows into
    ``StrandGroup`` records, preserving insertion (== query) order.
    """
    strands: dict[str, list[ExpectationItem]] = {}
    for exp, strand_name in rows:
        if strand_name not in strands:
            strands[strand_name] = []
        strands[strand_name].append(ExpectationItem(
            code=exp.ministry_code,
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
    injection.
    """
    course_code, rows = _load_course_expectations(db, course_code)
    # Use the max grade across the subject's expectations (matches the
    # /courses aggregation choice). Phase-2 used the first row's grade
    # under the same 1:1 invariant.
    grade_level = max(exp.grade for exp, _ in rows)
    return CurriculumCourseResponse(
        course_code=course_code,
        grade_level=grade_level,
        strands=_group_by_strand(rows),
    )


@router.get("/{course_code}", response_model=CurriculumCourseResponse)
def get_curriculum_for_course(
    course_code: str,
    _user: User = Depends(require_cmcp_enabled),
    db: Session = Depends(get_db),
):
    """Return all expectations for a subject, grouped by strand.

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
    """Search expectations for a subject by keyword (case-insensitive substring match).

    Returns the same grouped structure as ``GET /{course_code}``, but
    only including expectations whose description **or** ministry code
    contains the query string. An empty / missing ``q`` falls through
    to the un-filtered course view. A query that matches no expectations
    returns the course shell with an empty ``strands`` list — *not* a
    404 — so the UI can render a "no matches" state.
    """
    course_code = course_code.upper()

    if not q or not q.strip():
        return _build_course_response(db, course_code)

    q_pattern = f"%{q.strip()}%"

    rows = (
        db.query(
            CEGExpectation,
            CEGStrand.name.label("strand_name"),
        )
        .join(CEGStrand, CEGExpectation.strand_id == CEGStrand.id)
        .join(CEGSubject, CEGExpectation.subject_id == CEGSubject.id)
        .filter(
            func.upper(CEGSubject.code) == course_code,
            CEGExpectation.active.is_(True),
            CEGExpectation.review_state == "accepted",
            or_(
                CEGExpectation.description.ilike(q_pattern),
                CEGExpectation.ministry_code.ilike(q_pattern),
            ),
        )
        .order_by(CEGStrand.code, CEGExpectation.ministry_code)
        .all()
    )

    if not rows:
        # Empty result on a possibly-known subject — distinguish "subject
        # exists but no matches" (200 + empty strands) from "subject does
        # not exist" (404). The fallback also enforces active/review_state
        # so that a subject whose only expectations are pending/rejected
        # is treated as "unknown" from the public-surface perspective.
        any_row = (
            db.query(CEGExpectation.grade)
            .join(CEGSubject, CEGExpectation.subject_id == CEGSubject.id)
            .filter(
                func.upper(CEGSubject.code) == course_code,
                CEGExpectation.active.is_(True),
                CEGExpectation.review_state == "accepted",
            )
            .order_by(CEGExpectation.grade.desc())
            .first()
        )
        if not any_row:
            raise HTTPException(
                status_code=404,
                detail=f"No curriculum data found for course {course_code}",
            )
        return CurriculumCourseResponse(
            course_code=course_code,
            grade_level=any_row.grade,
            strands=[],
        )

    grade_level = max(exp.grade for exp, _ in rows)
    return CurriculumCourseResponse(
        course_code=course_code,
        grade_level=grade_level,
        strands=_group_by_strand(rows),
    )
