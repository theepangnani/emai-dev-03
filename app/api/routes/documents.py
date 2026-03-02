"""Central document repository endpoint.

GET /api/documents — returns all course materials (CourseContent + StudyGuides)
accessible to the current user across all their courses, with optional filters.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.api.deps import get_current_user, require_feature
from app.models.course import Course, student_courses
from app.models.course_content import CourseContent
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from pydantic import BaseModel
from datetime import datetime

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class DocumentItem(BaseModel):
    id: int
    title: str
    type: str  # "document" | "study_guide" | "quiz" | "flashcards"
    course_id: int
    course_name: str
    created_at: datetime
    has_study_guide: bool
    has_quiz: bool
    has_flashcards: bool
    child_name: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentsResponse(BaseModel):
    items: list[DocumentItem]
    total: int


# ---------------------------------------------------------------------------
# Helpers — reuse the logic from course_contents.py
# ---------------------------------------------------------------------------

def _get_visible_course_ids(db: Session, user: User, child_id: Optional[int] = None) -> list[int]:
    """Return course IDs visible to the user."""

    if user.role == UserRole.ADMIN:
        return [r[0] for r in db.query(Course.id).all()]

    if user.role == UserRole.STUDENT:
        created = db.query(Course.id).filter(Course.created_by_user_id == user.id).all()
        ids = {r[0] for r in created}
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if student:
            ids.update(c.id for c in student.courses)
        return list(ids)

    if user.role == UserRole.TEACHER:
        created = db.query(Course.id).filter(Course.created_by_user_id == user.id).all()
        ids = {r[0] for r in created}
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if teacher:
            taught = db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
            ids.update(r[0] for r in taught)
        return list(ids)

    if user.role == UserRole.PARENT:
        # Get children's student IDs
        child_rows = db.query(parent_students.c.student_id).filter(
            parent_students.c.parent_id == user.id
        ).all()
        child_sids = [r[0] for r in child_rows]

        if child_id is not None:
            # Filter to a specific child by student_id
            if child_id not in child_sids:
                return []
            child_student = db.query(Student).filter(Student.id == child_id).first()
            if not child_student:
                return []
            ids = {c.id for c in child_student.courses}
            child_user_ids = db.query(Student.user_id).filter(Student.id == child_id).all()
            if child_user_ids:
                child_created = db.query(Course.id).filter(
                    Course.created_by_user_id.in_([r[0] for r in child_user_ids])
                ).all()
                ids.update(r[0] for r in child_created)
            return list(ids)

        # No specific child — all children's courses
        created = db.query(Course.id).filter(Course.created_by_user_id == user.id).all()
        ids = {r[0] for r in created}
        if child_sids:
            enrolled = db.query(student_courses.c.course_id).filter(
                student_courses.c.student_id.in_(child_sids)
            ).all()
            ids.update(r[0] for r in enrolled)
            child_user_ids_rows = db.query(Student.user_id).filter(Student.id.in_(child_sids)).all()
            child_uids = [r[0] for r in child_user_ids_rows]
            if child_uids:
                child_created = db.query(Course.id).filter(
                    Course.created_by_user_id.in_(child_uids)
                ).all()
                ids.update(r[0] for r in child_created)
        return list(ids)

    return []


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/", response_model=DocumentsResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_documents(
    request: Request,
    _flag=Depends(require_feature("document_repository")),
    course_id: Optional[int] = Query(None, description="Filter by course ID"),
    type: Optional[str] = Query(None, description="Filter by type: document, study_guide, quiz, flashcards"),
    search: Optional[str] = Query(None, description="Search by title (case-insensitive)"),
    child_id: Optional[int] = Query(None, description="For parents: filter by child student_id"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all course materials accessible to the current user, across all courses.

    Combines CourseContent records (type="document") and StudyGuide records
    (type=study_guide|quiz|flashcards). Each document item includes flags for
    whether the source document has associated AI-generated materials.

    For parents, each item includes the child's name for context.
    """
    # 1. Determine visible course IDs
    visible_ids = _get_visible_course_ids(db, current_user, child_id)
    if course_id is not None:
        # Restrict to the requested course only if the user can see it
        if course_id not in visible_ids:
            return DocumentsResponse(items=[], total=0)
        visible_ids = [course_id]

    if not visible_ids:
        return DocumentsResponse(items=[], total=0)

    # 2. Build a map: course_id -> Course for fast lookups (single query)
    courses_map: dict[int, Course] = {
        c.id: c
        for c in db.query(Course).filter(Course.id.in_(visible_ids)).all()
    }

    # 3. For parents: build child info maps for child_name annotation
    course_to_child_sids: dict[int, list[int]] = {}
    student_to_name: dict[int, str] = {}
    if current_user.role == UserRole.PARENT:
        child_rows = db.query(parent_students.c.student_id).filter(
            parent_students.c.parent_id == current_user.id
        ).all()
        child_sids = [r[0] for r in child_rows]
        if child_sids:
            enrolled = db.query(student_courses.c.course_id, student_courses.c.student_id).filter(
                student_courses.c.student_id.in_(child_sids)
            ).all()
            for cid, sid in enrolled:
                course_to_child_sids.setdefault(cid, []).append(sid)
            students = db.query(Student).filter(Student.id.in_(child_sids)).all()
            for s in students:
                name = s.user.full_name if s.user else f"Student #{s.id}"
                student_to_name[s.id] = name

    # 4. Fetch course contents (documents)
    items: list[DocumentItem] = []

    filter_type = (type or "").strip().lower()

    if not filter_type or filter_type == "document":
        cc_query = (
            db.query(CourseContent)
            .filter(
                CourseContent.course_id.in_(visible_ids),
                CourseContent.archived_at.is_(None),
            )
        )
        if search:
            cc_query = cc_query.filter(CourseContent.title.ilike(f"%{search}%"))

        course_contents = cc_query.order_by(CourseContent.created_at.desc()).all()

        # Batch-load study guide presence for all content IDs in one query
        cc_ids = [cc.id for cc in course_contents]
        guide_rows: list[tuple[int, str]] = []
        if cc_ids:
            guide_rows = (
                db.query(StudyGuide.course_content_id, StudyGuide.guide_type)
                .filter(
                    StudyGuide.course_content_id.in_(cc_ids),
                    StudyGuide.archived_at.is_(None),
                )
                .all()
            )

        # Build sets per content_id
        has_study_guide_ids: set[int] = set()
        has_quiz_ids: set[int] = set()
        has_flashcards_ids: set[int] = set()
        for content_id, guide_type in guide_rows:
            if guide_type == "study_guide":
                has_study_guide_ids.add(content_id)
            elif guide_type == "quiz":
                has_quiz_ids.add(content_id)
            elif guide_type == "flashcards":
                has_flashcards_ids.add(content_id)

        for cc in course_contents:
            course = courses_map.get(cc.course_id)
            course_name = course.name if course else f"Course #{cc.course_id}"

            child_name: Optional[str] = None
            if current_user.role == UserRole.PARENT:
                for sid in course_to_child_sids.get(cc.course_id, []):
                    if sid in student_to_name:
                        child_name = student_to_name[sid]
                        break

            items.append(DocumentItem(
                id=cc.id,
                title=cc.title,
                type="document",
                course_id=cc.course_id,
                course_name=course_name,
                created_at=cc.created_at,
                has_study_guide=cc.id in has_study_guide_ids,
                has_quiz=cc.id in has_quiz_ids,
                has_flashcards=cc.id in has_flashcards_ids,
                child_name=child_name,
            ))

    # 5. Fetch study guides / quizzes / flashcards
    valid_guide_types = {"study_guide", "quiz", "flashcards"}
    if filter_type in valid_guide_types:
        # Specific guide type requested
        requested_guide_types: list[str] = [filter_type]
    elif filter_type == "document":
        # Documents only — skip guides entirely
        requested_guide_types = []
    else:
        # No type filter or unrecognised value — include all guide types
        requested_guide_types = list(valid_guide_types)

    if requested_guide_types:
        sg_query = (
            db.query(StudyGuide)
            .filter(
                StudyGuide.course_id.in_(visible_ids),
                StudyGuide.guide_type.in_(requested_guide_types),
                StudyGuide.archived_at.is_(None),
            )
        )
        if search:
            sg_query = sg_query.filter(StudyGuide.title.ilike(f"%{search}%"))

        study_guides = sg_query.order_by(StudyGuide.created_at.desc()).all()

        for sg in study_guides:
            cid = sg.course_id
            course = courses_map.get(cid) if cid else None
            course_name = course.name if course else "Unknown Course"
            course_display_id = cid or 0

            child_name = None
            if current_user.role == UserRole.PARENT and cid:
                for sid in course_to_child_sids.get(cid, []):
                    if sid in student_to_name:
                        child_name = student_to_name[sid]
                        break

            items.append(DocumentItem(
                id=sg.id,
                title=sg.title,
                type=sg.guide_type,
                course_id=course_display_id,
                course_name=course_name,
                created_at=sg.created_at,
                has_study_guide=False,
                has_quiz=False,
                has_flashcards=False,
                child_name=child_name,
            ))

    # 6. Sort combined list by created_at descending
    items.sort(key=lambda x: x.created_at, reverse=True)

    total = len(items)
    paginated = items[offset: offset + limit]

    return DocumentsResponse(items=paginated, total=total)
