"""
Ontario Curriculum Management API (#571).

Routes:
  GET /api/curriculum/courses                      — list all seeded course codes
  GET /api/curriculum/{course_code}                — get all expectations grouped by strand
  GET /api/curriculum/{course_code}/search?q=      — keyword search within a course
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_feature
from app.db.database import get_db
from app.models.curriculum import CurriculumExpectation
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/curriculum", tags=["Ontario Curriculum"])


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
    _flag=Depends(require_feature("course_planning")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all course codes that have seeded curriculum expectations."""
    rows = (
        db.query(
            CurriculumExpectation.course_code,
            CurriculumExpectation.grade_level,
        )
        .distinct(CurriculumExpectation.course_code)
        .order_by(CurriculumExpectation.course_code)
        .all()
    )

    result = []
    for row in rows:
        count = (
            db.query(CurriculumExpectation)
            .filter(CurriculumExpectation.course_code == row.course_code)
            .count()
        )
        result.append(CourseListItem(
            course_code=row.course_code,
            grade_level=row.grade_level,
            expectation_count=count,
        ))
    return result


# ---------------------------------------------------------------------------
# GET /api/curriculum/{course_code}
# ---------------------------------------------------------------------------

@router.get("/{course_code}", response_model=CurriculumCourseResponse)
def get_curriculum_for_course(
    course_code: str,
    _flag=Depends(require_feature("course_planning")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all expectations for a course, grouped by strand.

    Returns { course_code, grade_level, strands: [{ name, expectations: [{code, description, type}] }] }
    """
    course_code = course_code.upper()
    expectations = (
        db.query(CurriculumExpectation)
        .filter(CurriculumExpectation.course_code == course_code)
        .order_by(CurriculumExpectation.strand, CurriculumExpectation.expectation_code)
        .all()
    )

    if not expectations:
        raise HTTPException(status_code=404, detail=f"No curriculum data found for course {course_code}")

    grade_level = expectations[0].grade_level

    # Group by strand
    strands: dict[str, list[ExpectationItem]] = {}
    for exp in expectations:
        if exp.strand not in strands:
            strands[exp.strand] = []
        strands[exp.strand].append(ExpectationItem(
            code=exp.expectation_code,
            description=exp.description,
            type=exp.expectation_type,
        ))

    strand_list = [
        StrandGroup(name=name, expectations=items)
        for name, items in strands.items()
    ]

    return CurriculumCourseResponse(
        course_code=course_code,
        grade_level=grade_level,
        strands=strand_list,
    )


# ---------------------------------------------------------------------------
# GET /api/curriculum/{course_code}/search
# ---------------------------------------------------------------------------

@router.get("/{course_code}/search", response_model=CurriculumCourseResponse)
def search_curriculum_expectations(
    course_code: str,
    q: Optional[str] = Query(None, min_length=1, max_length=200),
    _flag=Depends(require_feature("course_planning")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search expectations for a course by keyword (case-insensitive substring match).

    Returns the same grouped structure as GET /{course_code}, but only including
    expectations whose description contains the query string.
    """
    course_code = course_code.upper()

    if not q or not q.strip():
        return get_curriculum_for_course(course_code, db=db, current_user=current_user)

    q_lower = q.strip().lower()

    expectations = (
        db.query(CurriculumExpectation)
        .filter(
            CurriculumExpectation.course_code == course_code,
            or_(
                CurriculumExpectation.description.ilike(f"%{q_lower}%"),
                CurriculumExpectation.expectation_code.ilike(f"%{q_lower}%"),
            ),
        )
        .order_by(CurriculumExpectation.strand, CurriculumExpectation.expectation_code)
        .all()
    )

    if not expectations:
        # Return empty result rather than 404 for search
        all_exp = (
            db.query(CurriculumExpectation)
            .filter(CurriculumExpectation.course_code == course_code)
            .first()
        )
        if not all_exp:
            raise HTTPException(status_code=404, detail=f"No curriculum data found for course {course_code}")
        return CurriculumCourseResponse(
            course_code=course_code,
            grade_level=all_exp.grade_level,
            strands=[],
        )

    grade_level = expectations[0].grade_level

    strands: dict[str, list[ExpectationItem]] = {}
    for exp in expectations:
        if exp.strand not in strands:
            strands[exp.strand] = []
        strands[exp.strand].append(ExpectationItem(
            code=exp.expectation_code,
            description=exp.description,
            type=exp.expectation_type,
        ))

    strand_list = [
        StrandGroup(name=name, expectations=items)
        for name, items in strands.items()
    ]

    return CurriculumCourseResponse(
        course_code=course_code,
        grade_level=grade_level,
        strands=strand_list,
    )
