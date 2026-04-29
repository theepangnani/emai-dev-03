"""CMCP student academic context — service layer (CB-CMCP-001 M1-B 1B-1, #4460).

Ported from phase-2 ``app/mcp/resources/student.py`` (779 LOC).  The
phase-2 source mounted these as FastAPI routes; this dev-03 port is a
plain service module — the eventual MCP resource exposure (M2-A) will
import these functions and wrap them with MCP tool decorators.

Adaptations vs. phase-2
-----------------------

- No ``APIRouter`` / ``@router.get`` decorators — plain functions with
  ``(student_id: int, db: Session, current_user: User)`` signatures.
- ``GradeEntry`` does not exist in dev-03 yet — the grade-entry code
  paths from phase-2 are dropped.  Per-assignment grades remain
  available via ``StudentAssignment``.
- ``ReportCard`` from phase-2 → ``SchoolReportCard`` in dev-03.  The
  dev-03 model lacks the ``status``/``overall_average``/``ai_strengths``
  /``ai_improvement_areas`` fields, so the report-card summary returns
  only the fields that exist (id, term, uploaded_at).
- ``Student`` in dev-03 has no ``study_streak_days``/``longest_streak``
  /``last_study_date`` columns — those keys are omitted from the
  profile payload.
- The ``get_student_summary`` and ``identify_knowledge_gaps`` AI tools
  from phase-2 are intentionally NOT ported (M2-B territory).

Functions
---------

- :func:`get_student_profile`         — enrolled courses + report-card summary
- :func:`get_student_assignments`     — per-assignment status + counts
- :func:`get_student_study_history`   — study guides + quiz results + averages
- :func:`get_student_weak_areas`      — courses where student averages < 70%

All four enforce RBAC via :func:`_assert_access` and cache results for
five minutes per (function, student_id) tuple.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignment import Assignment, StudentAssignment
from app.models.course import Course, student_courses
from app.models.quiz_result import QuizResult
from app.models.school_report_card import SchoolReportCard
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.teacher import Teacher
from app.models.user import User, UserRole

# ---------------------------------------------------------------------------
# 5-minute per-student response cache
# ---------------------------------------------------------------------------
# Phase-2 used a plain dict because functools.lru_cache cannot key on a
# mutable Session object.  Same trade-off here — entries expire after
# ``_CACHE_TTL`` seconds via lazy eviction in :func:`_cache_get`.

_CACHE_TTL = 300  # seconds
_cache: dict[str, tuple[float, Any]] = {}


def _cache_role_key(current_user: User) -> str:
    """Return a stable role tag for cache scoping.

    Role MUST participate in the cache key so that role-conditional
    payload fields (added by future stripes — e.g. teacher-only
    annotation, grade-publication gates) cannot serve a parent's
    payload to an admin or vice versa.  ``"none"`` covers users mid-
    onboarding whose ``role`` is NULL.
    """
    return current_user.role.value if current_user.role else "none"


def _cache_get(key: str) -> Any | None:
    """Return cached value for ``key`` if present and not expired, else ``None``."""
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return data


def _cache_set(key: str, data: Any) -> None:
    """Store ``data`` under ``key`` with the current monotonic timestamp."""
    _cache[key] = (time.monotonic(), data)


# ---------------------------------------------------------------------------
# RBAC helper
# ---------------------------------------------------------------------------


def _assert_access(current_user: User, student: Student, db: Session) -> None:
    """Raise HTTP 403 if ``current_user`` may not read ``student``'s data.

    Access matrix:
      ADMIN    — full access
      STUDENT  — self only (``student.user_id == current_user.id``)
      PARENT   — own children via ``parent_students`` join table
      TEACHER  — students enrolled in courses where the teacher is assigned
    """
    role = current_user.role

    if role == UserRole.ADMIN:
        return

    if role == UserRole.STUDENT:
        if student.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return

    if role == UserRole.PARENT:
        link = (
            db.query(parent_students)
            .filter(
                parent_students.c.parent_id == current_user.id,
                parent_students.c.student_id == student.id,
            )
            .first()
        )
        if not link:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return

    if role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if not teacher:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        course = (
            db.query(Course)
            .join(student_courses, Course.id == student_courses.c.course_id)
            .filter(
                student_courses.c.student_id == student.id,
                Course.teacher_id == teacher.id,
            )
            .first()
        )
        if not course:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


def _get_student_or_404(student_id: int, db: Session) -> Student:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    return student


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def get_student_profile(
    student_id: int,
    db: Session,
    current_user: User,
) -> dict:
    """Return the student's profile (enrolled courses + report-card summary).

    Maps to MCP resource ``student://profile/{student_id}`` once the M2-A
    server-side wrapper lands.
    """
    student = _get_student_or_404(student_id, db)
    _assert_access(current_user, student, db)

    cache_key = f"profile:{student_id}:{_cache_role_key(current_user)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    courses = (
        db.query(Course)
        .join(student_courses, Course.id == student_courses.c.course_id)
        .filter(student_courses.c.student_id == student_id)
        .all()
    )

    # Latest non-archived school report card (dev-03 has no status column)
    latest_rc = (
        db.query(SchoolReportCard)
        .filter(
            SchoolReportCard.student_id == student_id,
            SchoolReportCard.archived_at.is_(None),
        )
        .order_by(SchoolReportCard.created_at.desc())
        .first()
    )

    user = student.user
    profile = {
        "resource_uri": f"student://profile/{student_id}",
        "student_id": student_id,
        "name": user.full_name if user else None,
        "email": user.email if user else None,
        "grade_level": student.grade_level,
        "school_name": student.school_name,
        "enrolled_courses": [
            {"id": c.id, "name": c.name, "subject": c.subject} for c in courses
        ],
        "report_card_summary": {
            "id": latest_rc.id,
            "term": latest_rc.term,
            "school_year": latest_rc.school_year,
            "uploaded_at": latest_rc.created_at.isoformat() if latest_rc.created_at else None,
        } if latest_rc else None,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }

    _cache_set(cache_key, profile)
    return profile


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


def get_student_assignments(
    student_id: int,
    db: Session,
    current_user: User,
) -> dict:
    """Return the student's assignments with status and grade percentages."""
    student = _get_student_or_404(student_id, db)
    _assert_access(current_user, student, db)

    cache_key = f"assignments:{student_id}:{_cache_role_key(current_user)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    student_assignments = (
        db.query(StudentAssignment)
        .join(Assignment, StudentAssignment.assignment_id == Assignment.id)
        .filter(StudentAssignment.student_id == student_id)
        .order_by(Assignment.due_date.asc())
        .all()
    )

    now = datetime.now(timezone.utc)
    items = []
    for sa in student_assignments:
        a = sa.assignment
        due = a.due_date
        # SQLite (dev/test) returns naive datetimes from a
        # ``DateTime(timezone=True)`` column, while Postgres returns
        # aware ones — normalize both paths to UTC-aware so the overdue
        # check works identically in both environments.
        if due is not None:
            due_aware = due if due.tzinfo is not None else due.replace(tzinfo=timezone.utc)
            overdue = (
                due_aware < now
                and sa.status not in ("submitted", "graded")
            )
        else:
            overdue = False
        percentage: float | None = None
        if sa.grade is not None and a.max_points and a.max_points > 0:
            percentage = round(sa.grade / a.max_points * 100, 1)

        items.append({
            "assignment_id": a.id,
            "title": a.title,
            "description": a.description,
            "course_id": a.course_id,
            "due_date": due.isoformat() if due else None,
            "status": sa.status,
            "grade": sa.grade,
            "max_points": a.max_points,
            "percentage": percentage,
            "is_late": sa.is_late,
            "overdue": overdue,
            "submitted_at": sa.submitted_at.isoformat() if sa.submitted_at else None,
        })

    result = {
        "resource_uri": f"student://assignments/{student_id}",
        "student_id": student_id,
        "total": len(items),
        "pending": sum(1 for i in items if i["status"] == "pending"),
        "submitted": sum(1 for i in items if i["status"] == "submitted"),
        "graded": sum(1 for i in items if i["status"] == "graded"),
        "overdue": sum(1 for i in items if i["overdue"]),
        "assignments": items,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }

    _cache_set(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# Study history
# ---------------------------------------------------------------------------


def get_student_study_history(
    student_id: int,
    db: Session,
    current_user: User,
) -> dict:
    """Return the student's study guide and quiz history with summary stats."""
    student = _get_student_or_404(student_id, db)
    _assert_access(current_user, student, db)

    cache_key = f"study_history:{student_id}:{_cache_role_key(current_user)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    user = student.user
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student user not found")

    guides = (
        db.query(StudyGuide)
        .filter(StudyGuide.user_id == user.id, StudyGuide.archived_at.is_(None))
        .order_by(StudyGuide.created_at.desc())
        .limit(50)
        .all()
    )

    quiz_results = (
        db.query(QuizResult)
        .filter(QuizResult.user_id == user.id)
        .order_by(QuizResult.completed_at.desc())
        .limit(100)
        .all()
    )

    avg_quiz_score: float | None = None
    if quiz_results:
        avg_quiz_score = round(
            sum(qr.percentage for qr in quiz_results) / len(quiz_results), 1
        )

    result = {
        "resource_uri": f"student://study-history/{student_id}",
        "student_id": student_id,
        "study_guides": [
            {
                "id": g.id,
                "title": g.title,
                "guide_type": g.guide_type,
                "course_id": g.course_id,
                "assignment_id": g.assignment_id,
                "created_at": g.created_at.isoformat() if g.created_at else None,
            }
            for g in guides
        ],
        "quiz_results": [
            {
                "id": qr.id,
                "study_guide_id": qr.study_guide_id,
                "score": qr.score,
                "total_questions": qr.total_questions,
                "percentage": qr.percentage,
                "attempt_number": qr.attempt_number,
                "completed_at": qr.completed_at.isoformat() if qr.completed_at else None,
            }
            for qr in quiz_results
        ],
        "summary": {
            "total_study_guides": len(guides),
            "total_quiz_attempts": len(quiz_results),
            "average_quiz_score": avg_quiz_score,
        },
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }

    _cache_set(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# Weak areas
# ---------------------------------------------------------------------------


def get_student_weak_areas(
    student_id: int,
    db: Session,
    current_user: User,
) -> dict:
    """Return courses where the student averages < 70%, sorted worst-first.

    Aggregates two signal sources:

    - Quiz results joined to their study guide's ``course_id``.
    - ``StudentAssignment`` grades converted to percentages via
      ``Assignment.max_points``.

    Each course's combined samples are averaged; courses with avg < 70%
    are returned with severity ``"high"`` (< 50%) or ``"medium"``.
    """
    student = _get_student_or_404(student_id, db)
    _assert_access(current_user, student, db)

    cache_key = f"weak_areas:{student_id}:{_cache_role_key(current_user)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    user = student.user
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student user not found")

    # Quiz scores aggregated per course (via study_guide.course_id)
    quiz_results = (
        db.query(QuizResult)
        .join(StudyGuide, QuizResult.study_guide_id == StudyGuide.id)
        .filter(QuizResult.user_id == user.id)
        .all()
    )

    course_scores: dict[int | None, list[float]] = {}
    guide_ids = {qr.study_guide_id for qr in quiz_results}
    guides_by_id: dict[int, StudyGuide] = {}
    if guide_ids:
        for g in db.query(StudyGuide).filter(StudyGuide.id.in_(guide_ids)).all():
            guides_by_id[g.id] = g

    for qr in quiz_results:
        guide = guides_by_id.get(qr.study_guide_id)
        cid = guide.course_id if guide else None
        course_scores.setdefault(cid, []).append(qr.percentage)

    # Per-assignment grade percentages aggregated per course
    student_assignments = (
        db.query(StudentAssignment)
        .join(Assignment, StudentAssignment.assignment_id == Assignment.id)
        .filter(
            StudentAssignment.student_id == student_id,
            StudentAssignment.grade.isnot(None),
        )
        .all()
    )
    sa_by_course: dict[int, list[float]] = {}
    for sa in student_assignments:
        a = sa.assignment
        if a.max_points and a.max_points > 0 and sa.grade is not None:
            pct = sa.grade / a.max_points * 100
            sa_by_course.setdefault(a.course_id, []).append(pct)

    # Resolve course names for any course id we'll surface
    all_course_ids: set[int] = set()
    for cid in course_scores.keys():
        if cid is not None:
            all_course_ids.add(cid)
    all_course_ids.update(sa_by_course.keys())

    courses_map: dict[int, Course] = {}
    if all_course_ids:
        for c in db.query(Course).filter(Course.id.in_(all_course_ids)).all():
            courses_map[c.id] = c

    # Build weak-area entries
    weak_areas = []
    for cid in all_course_ids:
        all_scores: list[float] = []
        all_scores.extend(course_scores.get(cid, []))
        all_scores.extend(sa_by_course.get(cid, []))

        if not all_scores:
            continue

        avg = sum(all_scores) / len(all_scores)
        if avg < 70.0:
            course = courses_map.get(cid)
            severity = "high" if avg < 50 else "medium"
            weak_areas.append({
                "course_id": cid,
                "course_name": course.name if course else "Unknown",
                "subject": course.subject if course else None,
                "average_score": round(avg, 1),
                "sample_count": len(all_scores),
                "severity": severity,
            })

    weak_areas.sort(key=lambda x: x["average_score"])

    result = {
        "resource_uri": f"student://weak-areas/{student_id}",
        "student_id": student_id,
        "weak_areas": weak_areas,
        "total_weak_areas": len(weak_areas),
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }

    _cache_set(cache_key, result)
    return result
