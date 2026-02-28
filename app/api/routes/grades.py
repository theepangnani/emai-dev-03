"""Grade display endpoints for dashboards.

Provides:
- /grades/summary — per-child, per-course grade averages (parent) or per-course (student)
- /grades/course/{course_id} — all graded assignments for a specific course
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.analytics import GradeRecord
from app.models.assignment import Assignment
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/grades", tags=["Grades"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _percentage_to_letter(pct: float) -> str:
    """Convert a percentage to a letter grade."""
    if pct >= 90:
        return "A"
    elif pct >= 80:
        return "B"
    elif pct >= 70:
        return "C"
    elif pct >= 60:
        return "D"
    return "F"


def _grade_color(letter: str) -> str:
    """Return a CSS-friendly color category for letter grades."""
    if letter in ("A", "B"):
        return "green"
    elif letter == "C":
        return "yellow"
    return "red"


def _compute_course_grade_data(db: Session, student_id: int, course_id: int | None = None) -> list[dict]:
    """Compute per-course grade averages for a student."""
    query = (
        db.query(
            GradeRecord.course_id,
            Course.name,
            sa_func.count(GradeRecord.id).label("graded_count"),
            sa_func.avg(GradeRecord.percentage).label("avg_pct"),
        )
        .join(Course, GradeRecord.course_id == Course.id)
        .filter(GradeRecord.student_id == student_id)
    )
    if course_id:
        query = query.filter(GradeRecord.course_id == course_id)

    query = query.group_by(GradeRecord.course_id, Course.name)
    rows = query.all()

    result = []
    for row in rows:
        cid, cname, graded_count, avg_pct = row
        avg_pct = round(float(avg_pct or 0), 1)
        # Count total assignments in this course
        total_assignments = (
            db.query(sa_func.count(Assignment.id))
            .filter(Assignment.course_id == cid)
            .scalar()
        ) or 0
        letter = _percentage_to_letter(avg_pct)
        result.append({
            "course_id": cid,
            "course_name": cname,
            "assignment_count": total_assignments,
            "graded_count": graded_count,
            "average_grade": avg_pct,
            "letter_grade": letter,
            "color": _grade_color(letter),
        })

    return result


def _get_student_ids_for_user(db: Session, current_user: User) -> list[tuple[int, str]]:
    """Return list of (student_id, student_name) the user can view grades for."""
    if current_user.has_role(UserRole.STUDENT):
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student:
            return [(student.id, current_user.full_name or "Student")]
        return []

    if current_user.has_role(UserRole.PARENT):
        rows = db.execute(
            parent_students.select().where(parent_students.c.parent_id == current_user.id)
        ).fetchall()
        result = []
        for row in rows:
            student = db.query(Student).filter(Student.id == row.student_id).first()
            if student and student.user:
                result.append((student.id, student.user.full_name or "Student"))
        return result

    if current_user.has_role(UserRole.ADMIN):
        students = db.query(Student).all()
        return [(s.id, s.user.full_name if s.user else "Student") for s in students]

    return []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/summary")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_grade_summary(
    request: Request,
    student_id: int | None = Query(None, description="Filter by student ID (parents can specify a child)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Grade summary for dashboard display.

    - Parents: returns per-child, per-course grade averages
    - Students: returns per-course grade averages for themselves
    - Admins: can specify any student_id
    """
    if student_id:
        # Verify access
        allowed = _get_student_ids_for_user(db, current_user)
        allowed_ids = [sid for sid, _ in allowed]
        if student_id not in allowed_ids and not current_user.has_role(UserRole.ADMIN):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this student's grades")
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

        courses = _compute_course_grade_data(db, student_id)
        overall = round(sum(c["average_grade"] for c in courses) / len(courses), 1) if courses else 0.0
        letter = _percentage_to_letter(overall)

        return {
            "children": [{
                "student_id": student_id,
                "student_name": student.user.full_name if student.user else "Student",
                "overall_average": overall,
                "letter_grade": letter,
                "color": _grade_color(letter),
                "courses": courses,
            }],
        }

    # No student_id specified — return all accessible students
    student_ids = _get_student_ids_for_user(db, current_user)
    if not student_ids:
        return {"children": []}

    children_data = []
    for sid, sname in student_ids:
        courses = _compute_course_grade_data(db, sid)
        overall = round(sum(c["average_grade"] for c in courses) / len(courses), 1) if courses else 0.0
        letter = _percentage_to_letter(overall)
        children_data.append({
            "student_id": sid,
            "student_name": sname,
            "overall_average": overall,
            "letter_grade": letter,
            "color": _grade_color(letter),
            "courses": courses,
        })

    return {"children": children_data}


@router.get("/course/{course_id}")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_course_grades(
    request: Request,
    course_id: int,
    student_id: int | None = Query(None, description="Filter by student ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all graded assignments for a specific course.

    Includes: assignment title, grade, max_grade, percentage, due_date, status.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # Determine which student(s) to query
    allowed = _get_student_ids_for_user(db, current_user)
    allowed_ids = [sid for sid, _ in allowed]

    if student_id:
        if student_id not in allowed_ids and not current_user.has_role(UserRole.ADMIN):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        target_ids = [student_id]
    else:
        target_ids = allowed_ids

    if not target_ids:
        return {"course_id": course_id, "course_name": course.name, "assignments": []}

    # Query GradeRecords for this course and these students
    records = (
        db.query(GradeRecord, Assignment)
        .outerjoin(Assignment, GradeRecord.assignment_id == Assignment.id)
        .filter(
            GradeRecord.course_id == course_id,
            GradeRecord.student_id.in_(target_ids),
        )
        .order_by(GradeRecord.recorded_at.desc())
        .all()
    )

    assignments_list = []
    for gr, assignment in records:
        pct = gr.percentage
        letter = _percentage_to_letter(pct)
        assignments_list.append({
            "grade_record_id": gr.id,
            "assignment_id": assignment.id if assignment else None,
            "assignment_title": assignment.title if assignment else f"{course.name} grade",
            "grade": gr.grade,
            "max_grade": gr.max_grade,
            "percentage": round(pct, 1),
            "letter_grade": letter,
            "color": _grade_color(letter),
            "due_date": assignment.due_date.isoformat() if assignment and assignment.due_date else None,
            "status": "graded",
            "student_id": gr.student_id,
            "recorded_at": gr.recorded_at.isoformat() if gr.recorded_at else None,
        })

    # Compute course average
    avg = round(sum(a["percentage"] for a in assignments_list) / len(assignments_list), 1) if assignments_list else 0.0
    letter = _percentage_to_letter(avg)

    return {
        "course_id": course_id,
        "course_name": course.name,
        "average_grade": avg,
        "letter_grade": letter,
        "color": _grade_color(letter),
        "total_graded": len(assignments_list),
        "assignments": assignments_list,
    }
