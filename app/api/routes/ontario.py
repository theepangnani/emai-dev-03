"""
Ontario course catalog and school board integration (#500, #511).

Routes:
  GET  /api/ontario/boards                     — list all active Ontario boards
  GET  /api/ontario/boards/{board_id}/courses  — courses for a board (+ universal), filterable
  GET  /api/ontario/courses/{course_code}      — detail for a single course
  POST /api/ontario/student/board              — link current student (or parent's child) to a board
  GET  /api/ontario/student/board              — get current student's board link
"""

import logging
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.database import get_db
from app.models.ontario_board import OntarioBoard
from app.models.course_catalog import CourseCatalogItem
from app.models.student_board import StudentBoard
from app.models.student import Student
from app.models.user import User, UserRole
from app.schemas.ontario import (
    OntarioBoardResponse,
    CourseCatalogResponse,
    CourseCatalogPage,
    StudentBoardLink,
    StudentBoardResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ontario", tags=["Ontario Course Catalog"])


# ---------------------------------------------------------------------------
# GET /api/ontario/boards
# ---------------------------------------------------------------------------

@router.get("/boards", response_model=list[OntarioBoardResponse])
def list_boards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all active Ontario school boards."""
    boards = db.query(OntarioBoard).filter(OntarioBoard.is_active == True).order_by(OntarioBoard.name).all()  # noqa: E712
    return boards


# ---------------------------------------------------------------------------
# GET /api/ontario/boards/{board_id}/courses
# ---------------------------------------------------------------------------

@router.get("/boards/{board_id}/courses", response_model=CourseCatalogPage)
def list_board_courses(
    board_id: int,
    grade: Optional[int] = Query(default=None, ge=9, le=12, description="Filter by grade level (9–12)"),
    subject: Optional[str] = Query(default=None, description="Filter by subject area (partial match)"),
    pathway: Optional[str] = Query(default=None, description="Filter by pathway code: U, C, M, E, O"),
    search: Optional[str] = Query(default=None, description="Search in course code or name"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return courses for a given board plus universal courses (board_id=NULL).
    Supports filtering by grade, subject, pathway, and free-text search.
    Results are paginated.
    """
    # Verify board exists
    board = db.query(OntarioBoard).filter(OntarioBoard.id == board_id).first()
    if not board:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

    # Base query: board-specific courses OR universal courses (board_id IS NULL)
    q = db.query(CourseCatalogItem).filter(
        or_(CourseCatalogItem.board_id == board_id, CourseCatalogItem.board_id == None)  # noqa: E711
    )

    if grade is not None:
        q = q.filter(CourseCatalogItem.grade_level == grade)
    if subject:
        q = q.filter(CourseCatalogItem.subject_area.ilike(f"%{subject}%"))
    if pathway:
        q = q.filter(CourseCatalogItem.pathway == pathway.upper())
    if search:
        term = f"%{search}%"
        q = q.filter(
            or_(
                CourseCatalogItem.course_code.ilike(term),
                CourseCatalogItem.course_name.ilike(term),
            )
        )

    total = q.count()
    pages = math.ceil(total / page_size) if total else 1
    items = (
        q.order_by(CourseCatalogItem.grade_level, CourseCatalogItem.subject_area, CourseCatalogItem.course_code)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return CourseCatalogPage(items=items, total=total, page=page, page_size=page_size, pages=pages)


# ---------------------------------------------------------------------------
# GET /api/ontario/courses/{course_code}
# ---------------------------------------------------------------------------

@router.get("/courses/{course_code}", response_model=CourseCatalogResponse)
def get_course_detail(
    course_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return details for a single course by course code.
    Prefers the universal (board_id=NULL) record; falls back to any board's record.
    """
    code = course_code.upper()
    course = (
        db.query(CourseCatalogItem)
        .filter(CourseCatalogItem.course_code == code, CourseCatalogItem.board_id == None)  # noqa: E711
        .first()
    )
    if not course:
        course = db.query(CourseCatalogItem).filter(CourseCatalogItem.course_code == code).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course '{code}' not found")
    return course


# ---------------------------------------------------------------------------
# POST /api/ontario/student/board
# ---------------------------------------------------------------------------

@router.post("/student/board", response_model=StudentBoardResponse, status_code=status.HTTP_201_CREATED)
def link_student_board(
    payload: StudentBoardLink,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Link a student to an Ontario board.

    - Students call without `student_id` to link themselves.
    - Parents call with `student_id` (must be their linked child).
    - Admins may link any student.
    """
    # Determine which student to link
    if current_user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    elif current_user.has_role(UserRole.PARENT):
        if not payload.student_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="student_id required for parents")
        student = db.query(Student).filter(Student.id == payload.student_id).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
        # Verify parent-child link
        linked_student_ids = [s.id for s in db.query(Student).join(
            Student.parents
        ).filter(User.id == current_user.id).all()]
        if student.id not in linked_student_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your linked child")
    elif current_user.has_role(UserRole.ADMIN):
        if not payload.student_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="student_id required for admins")
        student = db.query(Student).filter(Student.id == payload.student_id).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Verify board exists
    board = db.query(OntarioBoard).filter(OntarioBoard.id == payload.board_id, OntarioBoard.is_active == True).first()  # noqa: E712
    if not board:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found or inactive")

    # Upsert: update existing link or create new one
    existing = db.query(StudentBoard).filter(StudentBoard.student_id == student.id).first()
    if existing:
        existing.board_id = payload.board_id
        existing.school_name = payload.school_name
        db.commit()
        db.refresh(existing)
        return existing
    else:
        link = StudentBoard(
            student_id=student.id,
            board_id=payload.board_id,
            school_name=payload.school_name,
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        return link


# ---------------------------------------------------------------------------
# GET /api/ontario/student/board
# ---------------------------------------------------------------------------

@router.get("/student/board", response_model=StudentBoardResponse)
def get_student_board(
    student_id: Optional[int] = Query(default=None, description="For parents/admins: specify the student"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve the current student's (or a specified student's) board link.
    Students see their own. Parents/Admins may pass student_id.
    """
    if current_user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student profile not found")
    elif current_user.has_role(UserRole.PARENT) or current_user.has_role(UserRole.ADMIN):
        if not student_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="student_id query param required")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
        if current_user.has_role(UserRole.PARENT):
            linked_student_ids = [s.id for s in db.query(Student).join(
                Student.parents
            ).filter(User.id == current_user.id).all()]
            if student.id not in linked_student_ids:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your linked child")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    link = db.query(StudentBoard).filter(StudentBoard.student_id == student.id).first()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No board linked for this student")
    return link
