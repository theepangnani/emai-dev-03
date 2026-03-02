"""
MCP Student Academic Context Resources (#906).

Exposes read-only student data as MCP-addressable resources:

    student://profile/{student_id}
    student://assignments/{student_id}
    student://study-history/{student_id}
    student://weak-areas/{student_id}

Plus two MCP tools:
    get_student_summary        — GPT-powered natural-language academic summary
    identify_knowledge_gaps    — Topic-level gap analysis with severity ratings

All endpoints are FastAPI GET handlers served under:
    /api/mcp/resources/student/{student_id}/...
    /api/mcp/tools/student/{student_id}/...

RBAC:
    STUDENT  — self only (student.user_id == current_user.id)
    PARENT   — own children via parent_students join table
    TEACHER  — students enrolled in courses where teacher is assigned
    ADMIN    — all students
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.logging_config import get_logger
from app.models.assignment import Assignment, StudentAssignment
from app.models.course import Course, student_courses
from app.models.grade_entry import GradeEntry
from app.models.quiz_result import QuizResult
from app.models.report_card import ReportCard
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.services.ai_service import generate_content

logger = get_logger(__name__)

router = APIRouter(
    prefix="/mcp/resources/student",
    tags=["mcp-student-resources"],
)

tools_router = APIRouter(
    prefix="/mcp/tools/student",
    tags=["mcp-student-tools"],
)

# ---------------------------------------------------------------------------
# 5-minute per-student response cache
# ---------------------------------------------------------------------------
# We cannot use functools.lru_cache with mutable DB sessions, so we maintain
# a plain dict: {cache_key: (timestamp, data)}.  Entries expire after 300 s.

_CACHE_TTL = 300  # seconds
_cache: dict[str, tuple[float, Any]] = {}


def _cache_get(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return data


def _cache_set(key: str, data: Any) -> None:
    _cache[key] = (time.monotonic(), data)


# ---------------------------------------------------------------------------
# RBAC helper
# ---------------------------------------------------------------------------


def _assert_access(current_user: User, student: Student, db: Session) -> None:
    """Raise HTTP 403 if *current_user* is not allowed to read *student*'s data."""
    role = current_user.role

    if role == UserRole.ADMIN:
        return  # full access

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
        # Teacher must be assigned to at least one course the student is enrolled in
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
# Resource: student://profile/{student_id}
# ---------------------------------------------------------------------------


@router.get("/{student_id}/profile", summary="Student profile resource")
def get_student_profile(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the student's profile data (MCP resource: student://profile/{student_id})."""
    student = _get_student_or_404(student_id, db)
    _assert_access(current_user, student, db)

    cache_key = f"profile:{student_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Fetch enrolled courses
    courses = (
        db.query(Course)
        .join(student_courses, Course.id == student_courses.c.course_id)
        .filter(student_courses.c.student_id == student_id)
        .all()
    )

    # Latest grade entries (published only for non-admin/non-teacher)
    grades_q = (
        db.query(GradeEntry)
        .filter(GradeEntry.student_id == student_id)
    )
    if current_user.role not in (UserRole.ADMIN, UserRole.TEACHER):
        grades_q = grades_q.filter(GradeEntry.is_published.is_(True))
    grade_entries = grades_q.all()

    overall_avg: float | None = None
    if grade_entries:
        scored = [g.grade for g in grade_entries if g.grade is not None]
        overall_avg = round(sum(scored) / len(scored), 1) if scored else None

    # Report card summary
    latest_rc = (
        db.query(ReportCard)
        .filter(ReportCard.student_id == student_id, ReportCard.status == "analyzed")
        .order_by(ReportCard.uploaded_at.desc())
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
        "study_streak_days": student.study_streak_days,
        "longest_streak": student.longest_streak,
        "last_study_date": student.last_study_date.isoformat() if student.last_study_date else None,
        "enrolled_courses": [
            {"id": c.id, "name": c.name, "subject": c.subject} for c in courses
        ],
        "overall_average": overall_avg,
        "report_card_summary": {
            "term": latest_rc.term if latest_rc else None,
            "overall_average": latest_rc.overall_average if latest_rc else None,
            "ai_strengths": latest_rc.ai_strengths if latest_rc else None,
            "ai_improvement_areas": latest_rc.ai_improvement_areas if latest_rc else None,
        } if latest_rc else None,
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }

    _cache_set(cache_key, profile)
    return profile


# ---------------------------------------------------------------------------
# Resource: student://assignments/{student_id}
# ---------------------------------------------------------------------------


@router.get("/{student_id}/assignments", summary="Student assignments resource")
def get_student_assignments(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the student's assignment list with status and grades
    (MCP resource: student://assignments/{student_id})."""
    student = _get_student_or_404(student_id, db)
    _assert_access(current_user, student, db)

    cache_key = f"assignments:{student_id}"
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
        overdue = (
            due is not None
            and due.tzinfo is not None
            and due < now
            and sa.status not in ("submitted", "graded")
        )
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
# Resource: student://study-history/{student_id}
# ---------------------------------------------------------------------------


@router.get("/{student_id}/study-history", summary="Student study history resource")
def get_student_study_history(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the student's study guide and quiz history
    (MCP resource: student://study-history/{student_id})."""
    student = _get_student_or_404(student_id, db)
    _assert_access(current_user, student, db)

    cache_key = f"study_history:{student_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    user = student.user
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student user not found")

    # Study guides generated by this student (user_id)
    guides = (
        db.query(StudyGuide)
        .filter(StudyGuide.user_id == user.id, StudyGuide.archived_at.is_(None))
        .order_by(StudyGuide.created_at.desc())
        .limit(50)
        .all()
    )

    # Quiz results
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
            "study_streak_days": student.study_streak_days,
        },
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }

    _cache_set(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# Resource: student://weak-areas/{student_id}
# ---------------------------------------------------------------------------


@router.get("/{student_id}/weak-areas", summary="Student weak areas resource")
def get_student_weak_areas(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return courses/topics where the student is underperforming
    (MCP resource: student://weak-areas/{student_id})."""
    student = _get_student_or_404(student_id, db)
    _assert_access(current_user, student, db)

    cache_key = f"weak_areas:{student_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    user = student.user
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student user not found")

    # Aggregate quiz scores per study guide → course
    quiz_results = (
        db.query(QuizResult)
        .join(StudyGuide, QuizResult.study_guide_id == StudyGuide.id)
        .filter(QuizResult.user_id == user.id)
        .all()
    )

    # Group by course (via study guide course_id)
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

    # Grade entries for assignment-level performance
    grade_entries = (
        db.query(GradeEntry)
        .filter(GradeEntry.student_id == student_id)
    )
    if current_user.role not in (UserRole.ADMIN, UserRole.TEACHER):
        grade_entries = grade_entries.filter(GradeEntry.is_published.is_(True))
    grade_entries = grade_entries.all()

    grade_by_course: dict[int, list[float]] = {}
    for ge in grade_entries:
        if ge.grade is not None:
            grade_by_course.setdefault(ge.course_id, []).append(ge.grade)

    # Fetch course names
    all_course_ids = set(course_scores.keys()) | set(grade_by_course.keys())
    all_course_ids.discard(None)
    courses_map: dict[int, Course] = {}
    if all_course_ids:
        for c in db.query(Course).filter(Course.id.in_(all_course_ids)).all():
            courses_map[c.id] = c

    # Student assignments with low scores
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

    # Build weak-area entries (avg < 70%)
    weak_areas = []
    all_cids = set(course_scores.keys()) | set(grade_by_course.keys()) | set(sa_by_course.keys())
    all_cids.discard(None)

    for cid in all_cids:
        all_scores: list[float] = []
        all_scores.extend(course_scores.get(cid, []))  # type: ignore[arg-type]
        all_scores.extend(grade_by_course.get(cid, []))
        all_scores.extend(sa_by_course.get(cid, []))

        if not all_scores:
            continue

        avg = sum(all_scores) / len(all_scores)
        if avg < 70.0:
            course = courses_map.get(cid)  # type: ignore[arg-type]
            severity = "high" if avg < 50 else "medium"
            weak_areas.append({
                "course_id": cid,
                "course_name": course.name if course else "Unknown",
                "subject": course.subject if course else None,
                "average_score": round(avg, 1),
                "sample_count": len(all_scores),
                "severity": severity,
            })

    # Sort by average score ascending (worst first)
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


# ---------------------------------------------------------------------------
# Tool: get_student_summary
# ---------------------------------------------------------------------------


@tools_router.get("/{student_id}/summary", summary="Get student academic summary (AI)")
async def get_student_summary(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Generate a natural-language academic standing summary for the student using AI.

    MCP tool: get_student_summary
    """
    student = _get_student_or_404(student_id, db)
    _assert_access(current_user, student, db)

    cache_key = f"summary:{student_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Gather context data (reuse resource handlers but go direct to DB to avoid
    # re-doing auth checks inside the same request)
    user = student.user

    # Assignments
    student_assignments = (
        db.query(StudentAssignment)
        .join(Assignment, StudentAssignment.assignment_id == Assignment.id)
        .filter(StudentAssignment.student_id == student_id)
        .all()
    )
    total = len(student_assignments)
    graded = [sa for sa in student_assignments if sa.status == "graded" and sa.grade is not None]
    pending = sum(1 for sa in student_assignments if sa.status == "pending")
    avg_grade: float | None = None
    if graded:
        pcts = []
        for sa in graded:
            a = sa.assignment
            if a.max_points and a.max_points > 0:
                pcts.append(sa.grade / a.max_points * 100)
        if pcts:
            avg_grade = round(sum(pcts) / len(pcts), 1)

    # Quiz performance
    quiz_results = (
        db.query(QuizResult)
        .filter(QuizResult.user_id == (user.id if user else -1))
        .order_by(QuizResult.completed_at.desc())
        .limit(20)
        .all()
    )
    avg_quiz: float | None = None
    if quiz_results:
        avg_quiz = round(sum(qr.percentage for qr in quiz_results) / len(quiz_results), 1)

    # Enrolled courses
    courses = (
        db.query(Course)
        .join(student_courses, Course.id == student_courses.c.course_id)
        .filter(student_courses.c.student_id == student_id)
        .all()
    )

    context = f"""Student: {user.full_name if user else 'Unknown'}
Grade Level: {student.grade_level or 'N/A'}
School: {student.school_name or 'N/A'}
Study Streak: {student.study_streak_days} days
Enrolled Courses: {', '.join(c.name for c in courses) or 'None'}
Total Assignments: {total} ({pending} pending)
Average Assignment Grade: {f'{avg_grade}%' if avg_grade is not None else 'N/A'}
Average Quiz Score: {f'{avg_quiz}%' if avg_quiz is not None else 'N/A'}
"""

    prompt = (
        f"Provide a concise 3-5 sentence academic standing summary for this student:\n\n{context}"
    )
    system_prompt = (
        "You are an educational assistant providing concise, encouraging academic summaries "
        "for students on a K-12 platform. Be factual, supportive, and actionable. "
        "Highlight strengths and suggest specific improvements where needed."
    )

    try:
        summary_text = await generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=300,
            temperature=0.5,
        )
    except Exception as exc:
        logger.error("AI summary generation failed for student %s: %s", student_id, exc)
        summary_text = (
            f"Academic summary unavailable. "
            f"Student has {total} assignments ({pending} pending) "
            f"with {'average grade of ' + str(avg_grade) + '%' if avg_grade else 'no graded work yet'}."
        )

    result = {
        "tool": "get_student_summary",
        "student_id": student_id,
        "student_name": user.full_name if user else None,
        "summary": summary_text,
        "stats": {
            "total_assignments": total,
            "pending_assignments": pending,
            "average_assignment_grade": avg_grade,
            "average_quiz_score": avg_quiz,
            "study_streak_days": student.study_streak_days,
            "enrolled_courses": len(courses),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _cache_set(cache_key, result)
    return result


# ---------------------------------------------------------------------------
# Tool: identify_knowledge_gaps
# ---------------------------------------------------------------------------


@tools_router.get("/{student_id}/knowledge-gaps", summary="Identify student knowledge gaps (AI)")
async def identify_knowledge_gaps(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Identify topic-level knowledge gaps with severity ratings using AI analysis.

    MCP tool: identify_knowledge_gaps
    """
    student = _get_student_or_404(student_id, db)
    _assert_access(current_user, student, db)

    cache_key = f"knowledge_gaps:{student_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    user = student.user

    # Collect quiz results with study guide titles
    quiz_results = (
        db.query(QuizResult, StudyGuide)
        .join(StudyGuide, QuizResult.study_guide_id == StudyGuide.id)
        .filter(QuizResult.user_id == (user.id if user else -1))
        .order_by(QuizResult.completed_at.desc())
        .limit(50)
        .all()
    )

    # Grade entries
    grade_entries = (
        db.query(GradeEntry)
        .filter(GradeEntry.student_id == student_id)
    )
    if current_user.role not in (UserRole.ADMIN, UserRole.TEACHER):
        grade_entries = grade_entries.filter(GradeEntry.is_published.is_(True))
    grade_entries = grade_entries.all()

    # Build performance data per topic/guide
    quiz_lines = []
    for qr, sg in quiz_results:
        quiz_lines.append(
            f"- '{sg.title}' (type: {sg.guide_type}): {qr.percentage:.0f}% on attempt {qr.attempt_number}"
        )

    grade_lines = []
    for ge in grade_entries:
        if ge.grade is not None:
            grade_lines.append(
                f"- {ge.term or 'General'} grade: {ge.grade:.0f}/{ge.max_grade:.0f}"
                + (f" ({ge.letter_grade})" if ge.letter_grade else "")
                + (f" — {ge.feedback[:80]}" if ge.feedback else "")
            )

    context_parts = []
    if quiz_lines:
        context_parts.append("Quiz Performance:\n" + "\n".join(quiz_lines))
    if grade_lines:
        context_parts.append("Grade Entries:\n" + "\n".join(grade_lines))

    if not context_parts:
        result = {
            "tool": "identify_knowledge_gaps",
            "student_id": student_id,
            "gaps": [],
            "message": "Insufficient performance data to identify knowledge gaps.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _cache_set(cache_key, result)
        return result

    context = "\n\n".join(context_parts)

    prompt = f"""Analyze this student's performance data and identify knowledge gaps.

{context}

For each identified gap, provide:
1. topic: the subject/concept area
2. severity: "high" (< 50%), "medium" (50-70%), or "low" (70-80%)
3. evidence: brief explanation based on the data
4. recommendation: one concrete study suggestion

Return a JSON array of gap objects. Return ONLY valid JSON, no extra text.
Example:
[
  {{
    "topic": "Quadratic Equations",
    "severity": "high",
    "evidence": "Scored 35% on quadratic equations quiz across 2 attempts",
    "recommendation": "Review factoring methods and the quadratic formula"
  }}
]"""

    system_prompt = (
        "You are an educational data analyst for a K-12 platform. "
        "Analyze student performance data and identify specific knowledge gaps. "
        "Be precise, evidence-based, and actionable. Return only valid JSON."
    )

    gaps: list[dict] = []
    try:
        import json as _json

        raw = await generate_content(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=800,
            temperature=0.3,
        )
        # Strip markdown code fences if present
        clean = raw.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:])
            if clean.endswith("```"):
                clean = clean[: clean.rfind("```")]
        gaps = _json.loads(clean.strip())
        if not isinstance(gaps, list):
            gaps = []
    except Exception as exc:
        logger.warning("Knowledge gap AI parse failed for student %s: %s", student_id, exc)
        # Fallback: derive gaps from raw quiz data
        for qr, sg in quiz_results:
            if qr.percentage < 70:
                gaps.append({
                    "topic": sg.title,
                    "severity": "high" if qr.percentage < 50 else "medium",
                    "evidence": f"Scored {qr.percentage:.0f}% on quiz attempt {qr.attempt_number}",
                    "recommendation": f"Review material for '{sg.title}' and retry the quiz.",
                })

    result = {
        "tool": "identify_knowledge_gaps",
        "student_id": student_id,
        "gaps": gaps,
        "total_gaps": len(gaps),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _cache_set(cache_key, result)
    return result
