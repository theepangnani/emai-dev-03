"""Sync grades from Google Classroom into StudentAssignment + GradeRecord.

Fetches student submissions via the Google Classroom API, updates
StudentAssignment status/grade fields, and upserts into GradeRecord
(the analytics source of truth).
"""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.analytics import GradeRecord
from app.models.assignment import Assignment, StudentAssignment
from app.models.course import Course, student_courses
from app.models.student import Student
from app.models.user import User
from app.services.google_classroom import (
    get_course_work,
    get_student_submissions,
    update_user_tokens,
)

logger = logging.getLogger(__name__)

# Google Classroom submission state → our status mapping
_STATE_MAP = {
    "NEW": "pending",
    "CREATED": "pending",
    "TURNED_IN": "submitted",
    "RETURNED": "graded",
    "RECLAIMED_BY_STUDENT": "submitted",
}


def sync_grades_for_course(user: User, course: Course, db: Session) -> dict:
    """Sync grades for a single course from Google Classroom.

    Fetches all coursework, then all submissions for each, and upserts
    into StudentAssignment.

    Returns {"synced": int, "errors": int}.
    """
    if not course.google_classroom_id:
        return {"synced": 0, "errors": 0}

    if not user.google_access_token:
        logger.warning(f"User {user.id} has no Google access token")
        return {"synced": 0, "errors": 0}

    # Fetch all coursework items for this course
    try:
        coursework_list, credentials = get_course_work(
            user.google_access_token,
            course.google_classroom_id,
            user.google_refresh_token,
        )
        update_user_tokens(user, credentials, db)
    except Exception as e:
        logger.warning(f"Failed to fetch coursework for course {course.id}: {e}")
        return {"synced": 0, "errors": 1}

    # Build lookup: google_classroom_id → Assignment
    assignments_by_gc_id = {}
    for a in db.query(Assignment).filter(
        Assignment.course_id == course.id,
        Assignment.google_classroom_id.isnot(None),
    ).all():
        assignments_by_gc_id[a.google_classroom_id] = a

    # Find students enrolled in this course (need student_id → Student mapping)
    enrolled_students = (
        db.query(Student)
        .join(student_courses, Student.id == student_courses.c.student_id)
        .filter(student_courses.c.course_id == course.id)
        .all()
    )
    # Map google_id → Student for matching submissions to our students
    students_by_user_id = {s.user_id: s for s in enrolled_students}

    synced = 0
    errors = 0

    for cw in coursework_list:
        cw_id = cw.get("id")
        if not cw_id:
            continue

        assignment = assignments_by_gc_id.get(cw_id)
        if not assignment:
            continue  # assignment not synced yet

        max_points = cw.get("maxPoints") or assignment.max_points
        if not max_points:
            continue  # can't compute percentage without max_points

        # Update assignment max_points if Google has it
        if cw.get("maxPoints") and assignment.max_points != cw["maxPoints"]:
            assignment.max_points = cw["maxPoints"]

        # Fetch submissions for this coursework
        try:
            submissions, credentials = get_student_submissions(
                user.google_access_token,
                course.google_classroom_id,
                cw_id,
                user.google_refresh_token,
            )
            update_user_tokens(user, credentials, db)
        except Exception as e:
            logger.warning(f"Failed to fetch submissions for coursework {cw_id}: {e}")
            errors += 1
            continue

        for sub in submissions:
            grade = sub.get("assignedGrade") or sub.get("draftGrade")
            state = sub.get("state", "NEW")
            our_status = _STATE_MAP.get(state, "pending")

            # Match submission to a student via userId
            sub_user_id = sub.get("userId")
            if not sub_user_id:
                continue

            # Find the student — Google Classroom userId is stored as google_id on User
            student = _find_student_for_submission(
                db, sub_user_id, students_by_user_id,
            )
            if not student:
                continue

            # Upsert StudentAssignment
            sa = db.query(StudentAssignment).filter(
                StudentAssignment.student_id == student.id,
                StudentAssignment.assignment_id == assignment.id,
            ).first()

            if not sa:
                sa = StudentAssignment(
                    student_id=student.id,
                    assignment_id=assignment.id,
                    status=our_status,
                )
                db.add(sa)

            sa.status = our_status
            if grade is not None:
                sa.grade = grade
                synced += 1

                # Copy to GradeRecord (analytics source of truth)
                _upsert_grade_record(
                    db,
                    student_id=student.id,
                    course_id=course.id,
                    assignment_id=assignment.id,
                    grade=grade,
                    max_grade=max_points,
                    source="google_classroom",
                )
            if state == "TURNED_IN" and not sa.submitted_at:
                sa.submitted_at = datetime.utcnow()

    db.commit()
    return {"synced": synced, "errors": errors}


def sync_grades_for_student(user: User, student: Student, db: Session) -> dict:
    """Sync grades across all Google Classroom courses for a student.

    The ``user`` must have valid Google tokens (typically the parent or the
    student themselves).
    """
    # Find all courses the student is enrolled in that came from Google Classroom
    courses = (
        db.query(Course)
        .join(student_courses, Course.id == student_courses.c.course_id)
        .filter(
            student_courses.c.student_id == student.id,
            Course.google_classroom_id.isnot(None),
        )
        .all()
    )

    total_synced = 0
    total_errors = 0

    for course in courses:
        result = sync_grades_for_course(user, course, db)
        total_synced += result["synced"]
        total_errors += result["errors"]

    return {"synced": total_synced, "errors": total_errors}


def _upsert_grade_record(
    db: Session,
    student_id: int,
    course_id: int,
    assignment_id: int | None,
    grade: float,
    max_grade: float,
    source: str = "manual",
) -> GradeRecord:
    """Create or update a GradeRecord for the given student+assignment."""
    existing = None
    if assignment_id:
        existing = db.query(GradeRecord).filter(
            GradeRecord.student_id == student_id,
            GradeRecord.assignment_id == assignment_id,
        ).first()

    percentage = round((grade / max_grade) * 100, 2) if max_grade else 0.0

    if existing:
        existing.grade = grade
        existing.max_grade = max_grade
        existing.percentage = percentage
        existing.source = source
        existing.recorded_at = datetime.utcnow()
        return existing

    gr = GradeRecord(
        student_id=student_id,
        course_id=course_id,
        assignment_id=assignment_id,
        grade=grade,
        max_grade=max_grade,
        percentage=percentage,
        source=source,
        recorded_at=datetime.utcnow(),
    )
    db.add(gr)
    return gr


def _find_student_for_submission(
    db: Session,
    google_user_id: str,
    students_by_user_id: dict[int, Student],
) -> Student | None:
    """Map a Google Classroom userId to our Student record."""
    # The google_user_id from submissions is the Google account ID.
    # Our User model stores google_id; find the User, then the Student.
    user = db.query(User).filter(User.google_id == google_user_id).first()
    if not user:
        return None
    return students_by_user_id.get(user.id)


