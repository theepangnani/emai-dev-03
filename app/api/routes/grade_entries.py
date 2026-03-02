"""Teacher grade & feedback entry endpoints (#665).

Provides:
- GET  /grade-entries/course/{course_id}  — teacher: student×assignment grade matrix
- PUT  /grade-entries/bulk                — teacher: atomic bulk upsert
- GET  /grade-entries/student/{student_id} — student/parent: published grades
- POST /grade-entries/publish/{course_id}  — teacher: publish all drafts + notify students
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.assignment import Assignment
from app.models.course import Course, student_courses
from app.models.grade_entry import GradeEntry, _letter_grade
from app.models.notification import Notification, NotificationType
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.api.deps import get_current_user, require_feature, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/grade-entries", tags=["Grade Entries"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class BulkEntryItem(BaseModel):
    student_id: int
    course_id: int
    assignment_id: Optional[int] = None
    term: Optional[str] = None
    grade: Optional[float] = None
    max_grade: Optional[float] = 100.0
    feedback: Optional[str] = None
    is_published: Optional[bool] = False


class BulkUpsertRequest(BaseModel):
    entries: list[BulkEntryItem]


# ---------------------------------------------------------------------------
# Helper: check teacher owns / teaches this course
# ---------------------------------------------------------------------------

def _assert_teacher_course_access(db: Session, teacher_user: User, course_id: int) -> Course:
    """Raise 403 if the teacher does not teach the given course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    # ADMIN can always access
    if teacher_user.has_role(UserRole.ADMIN):
        return course

    # Check teacher is assigned to the course (via teachers table) or created it
    teacher_linked = False
    if course.teacher and course.teacher.user_id == teacher_user.id:
        teacher_linked = True
    if course.created_by_user_id == teacher_user.id:
        teacher_linked = True

    if not teacher_linked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to grade this course")

    return course


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/course/{course_id}")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_course_grade_matrix(
    request: Request,
    course_id: int,
    _flag=Depends(require_feature("grade_tracking")),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Return a student×assignment grade matrix for the teacher.

    Response shape:
    {
        course_id, course_name,
        assignments: [{ id, title }],
        students: [
            {
                student_id, student_name,
                grades: { <assignment_id|"term:Fall 2025">: { id, grade, max_grade, letter_grade, feedback, is_published, term } }
            }
        ]
    }
    """
    course = _assert_teacher_course_access(db, current_user, course_id)

    # Assignments for this course
    assignments = (
        db.query(Assignment)
        .filter(Assignment.course_id == course_id)
        .order_by(Assignment.due_date.asc().nullslast(), Assignment.id.asc())
        .all()
    )

    # Students enrolled in this course
    enrolled_students = (
        db.query(Student)
        .join(student_courses, Student.id == student_courses.c.student_id)
        .filter(student_courses.c.course_id == course_id)
        .all()
    )

    # All grade entries for this course
    grade_entries = (
        db.query(GradeEntry)
        .filter(GradeEntry.course_id == course_id)
        .all()
    )

    # Build lookup: (student_id, assignment_id or None, term) -> GradeEntry
    entry_map: dict[tuple, GradeEntry] = {}
    for ge in grade_entries:
        key = (ge.student_id, ge.assignment_id, ge.term)
        entry_map[key] = ge

    students_data = []
    for student in enrolled_students:
        student_name = student.user.full_name if student.user else f"Student {student.id}"
        grades: dict[str, dict] = {}

        for asgn in assignments:
            key = (student.id, asgn.id, None)
            ge = entry_map.get(key)
            col_key = str(asgn.id)
            if ge:
                grades[col_key] = {
                    "id": ge.id,
                    "grade": ge.grade,
                    "max_grade": ge.max_grade,
                    "letter_grade": ge.letter_grade,
                    "feedback": ge.feedback,
                    "is_published": ge.is_published,
                    "term": ge.term,
                }
            else:
                grades[col_key] = None

        # Also include any term-only entries (assignment_id=None)
        term_entries = [ge for ge in grade_entries if ge.student_id == student.id and ge.assignment_id is None]
        for te in term_entries:
            col_key = f"term:{te.term}"
            grades[col_key] = {
                "id": te.id,
                "grade": te.grade,
                "max_grade": te.max_grade,
                "letter_grade": te.letter_grade,
                "feedback": te.feedback,
                "is_published": te.is_published,
                "term": te.term,
            }

        students_data.append({
            "student_id": student.id,
            "student_name": student_name,
            "grades": grades,
        })

    return {
        "course_id": course_id,
        "course_name": course.name,
        "assignments": [{"id": a.id, "title": a.title, "due_date": a.due_date.isoformat() if a.due_date else None} for a in assignments],
        "students": students_data,
    }


@router.put("/bulk")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def bulk_upsert_grades(
    request: Request,
    body: BulkUpsertRequest,
    _flag=Depends(require_feature("grade_tracking")),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Atomically upsert grade entries in a single transaction.

    For each entry: if a matching (student_id, assignment_id, term) row exists, update it.
    Otherwise create a new one. Rolls back the entire batch on any error.
    """
    if not body.entries:
        return {"updated": 0, "created": 0, "entries": []}

    # Verify teacher has access to all referenced courses
    course_ids = {e.course_id for e in body.entries}
    for cid in course_ids:
        _assert_teacher_course_access(db, current_user, cid)

    updated = 0
    created = 0
    result_entries = []

    try:
        for item in body.entries:
            # Normalise: if assignment_id=0 treat as None
            assignment_id = item.assignment_id if item.assignment_id else None
            term = item.term or None

            existing = (
                db.query(GradeEntry)
                .filter(
                    GradeEntry.student_id == item.student_id,
                    GradeEntry.assignment_id == assignment_id,
                    GradeEntry.term == term,
                )
                .first()
            )

            pct = None
            if item.grade is not None and item.max_grade and item.max_grade > 0:
                pct = (item.grade / item.max_grade) * 100.0
            letter = _letter_grade(pct)

            if existing:
                existing.grade = item.grade
                existing.max_grade = item.max_grade if item.max_grade is not None else existing.max_grade
                existing.letter_grade = letter
                existing.feedback = item.feedback
                if item.is_published is not None:
                    existing.is_published = item.is_published
                existing.course_id = item.course_id
                existing.teacher_user_id = current_user.id
                result_entries.append(existing)
                updated += 1
            else:
                new_entry = GradeEntry(
                    teacher_user_id=current_user.id,
                    student_id=item.student_id,
                    course_id=item.course_id,
                    assignment_id=assignment_id,
                    term=term,
                    grade=item.grade,
                    max_grade=item.max_grade if item.max_grade is not None else 100.0,
                    letter_grade=letter,
                    feedback=item.feedback,
                    is_published=item.is_published if item.is_published is not None else False,
                )
                db.add(new_entry)
                result_entries.append(new_entry)
                created += 1

        db.commit()

        # Refresh all to get IDs/timestamps
        for e in result_entries:
            db.refresh(e)

    except Exception as exc:
        db.rollback()
        logger.error("bulk_upsert_grades failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save grades")

    return {
        "updated": updated,
        "created": created,
        "entries": [
            {
                "id": e.id,
                "student_id": e.student_id,
                "course_id": e.course_id,
                "assignment_id": e.assignment_id,
                "term": e.term,
                "grade": e.grade,
                "max_grade": e.max_grade,
                "letter_grade": e.letter_grade,
                "feedback": e.feedback,
                "is_published": e.is_published,
            }
            for e in result_entries
        ],
    }


@router.get("/student/{student_id}")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_student_grades(
    request: Request,
    student_id: int,
    _flag=Depends(require_feature("grade_tracking")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return published teacher-entered grades for a student.

    - Students can only view their own grades.
    - Parents can view linked children's grades.
    - Teachers and admins can view any student.

    Groups by course → assignment. Only published entries are returned for
    non-teacher/admin callers.
    """
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    is_teacher_or_admin = current_user.has_role(UserRole.TEACHER) or current_user.has_role(UserRole.ADMIN)

    # Authorization check
    if not is_teacher_or_admin:
        if current_user.has_role(UserRole.STUDENT):
            own_student = db.query(Student).filter(Student.user_id == current_user.id).first()
            if not own_student or own_student.id != student_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        elif current_user.has_role(UserRole.PARENT):
            linked = db.execute(
                parent_students.select().where(parent_students.c.parent_id == current_user.id)
            ).fetchall()
            linked_ids = [row.student_id for row in linked]
            if student_id not in linked_ids:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")

    query = db.query(GradeEntry).filter(GradeEntry.student_id == student_id)

    # Non-teachers only see published grades
    if not is_teacher_or_admin:
        query = query.filter(GradeEntry.is_published == True)

    entries = query.order_by(GradeEntry.course_id, GradeEntry.assignment_id).all()

    # Group by course
    course_map: dict[int, dict] = {}
    for ge in entries:
        cid = ge.course_id
        if cid not in course_map:
            course_map[cid] = {
                "course_id": cid,
                "course_name": ge.course.name if ge.course else f"Course {cid}",
                "grades": [],
            }
        course_map[cid]["grades"].append({
            "id": ge.id,
            "assignment_id": ge.assignment_id,
            "assignment_title": ge.assignment.title if ge.assignment else None,
            "term": ge.term,
            "grade": ge.grade,
            "max_grade": ge.max_grade,
            "letter_grade": ge.letter_grade,
            "feedback": ge.feedback,
            "is_published": ge.is_published,
        })

    return {
        "student_id": student_id,
        "student_name": student.user.full_name if student.user else f"Student {student_id}",
        "courses": list(course_map.values()),
    }


@router.post("/publish/{course_id}")
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def publish_course_grades(
    request: Request,
    course_id: int,
    _flag=Depends(require_feature("grade_tracking")),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
):
    """Publish all draft grade entries for a course.

    Sets is_published=True for all entries in the course.
    Sends an in-app GRADE_POSTED notification to each affected student.
    """
    _assert_teacher_course_access(db, current_user, course_id)

    draft_entries = (
        db.query(GradeEntry)
        .filter(GradeEntry.course_id == course_id, GradeEntry.is_published == False)
        .all()
    )

    if not draft_entries:
        return {"published": 0, "message": "No draft grades to publish"}

    # Collect unique student IDs for notifications
    student_ids = list({ge.student_id for ge in draft_entries})

    # Mark all as published
    for ge in draft_entries:
        ge.is_published = True

    # Fetch course name for notification
    course = db.query(Course).filter(Course.id == course_id).first()
    course_name = course.name if course else f"Course {course_id}"

    # Send in-app notification to each affected student
    notifications_created = 0
    for sid in student_ids:
        student = db.query(Student).filter(Student.id == sid).first()
        if student and student.user_id:
            notif = Notification(
                user_id=student.user_id,
                type=NotificationType.GRADE_POSTED,
                title="Grades Published",
                content=f"Your grades for {course_name} have been published by your teacher.",
                link=f"/grades",
            )
            db.add(notif)
            notifications_created += 1

    db.commit()

    return {
        "published": len(draft_entries),
        "notifications_sent": notifications_created,
        "message": f"Published {len(draft_entries)} grade entries for {len(student_ids)} students",
    }
