"""Seed the grade_records table with demo grade data.

Only runs if the grade_records table has no rows (idempotent).
Assigns grades to the first student found, spread across their enrolled
courses.  Each course gets a series of grades over time to show trends.

Also creates corresponding StudentAssignment rows so the data is
consistent across both tables.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.analytics import GradeRecord
from app.models.assignment import Assignment, StudentAssignment
from app.models.course import Course, student_courses
from app.models.student import Student

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "analytics" / "seed_grades.json"


def seed_grades(db: Session) -> int:
    """Import grade records from seed_grades.json. Returns number of records created."""
    existing = db.query(GradeRecord).count()
    if existing > 0:
        logger.info(f"grade_records already has {existing} rows — skipping seed")
        return 0

    if not SEED_FILE.exists():
        logger.warning(f"Grade seed file not found: {SEED_FILE}")
        return 0

    # Find the first student with enrolled courses
    student = (
        db.query(Student)
        .join(student_courses, Student.id == student_courses.c.student_id)
        .first()
    )
    if not student:
        logger.info("No enrolled students found — skipping grade seed")
        return 0

    # Get courses the student is enrolled in
    courses = (
        db.query(Course)
        .join(student_courses, Course.id == student_courses.c.course_id)
        .filter(student_courses.c.student_id == student.id)
        .all()
    )
    if not courses:
        logger.info("Student has no courses — skipping grade seed")
        return 0

    # Load seed patterns
    with open(SEED_FILE, "r", encoding="utf-8") as f:
        entries = json.load(f)

    # Get assignments per course for linking
    assignments_by_course: dict[int, list[Assignment]] = {}
    for course in courses:
        assignments_by_course[course.id] = (
            db.query(Assignment)
            .filter(Assignment.course_id == course.id)
            .order_by(Assignment.created_at.asc())
            .all()
        )

    now = datetime.utcnow()
    count = 0

    for entry in entries:
        course_idx = entry["course_pattern"] % len(courses)
        course = courses[course_idx]
        assign_idx = entry.get("assignment_index", 0)
        course_assignments = assignments_by_course.get(course.id, [])

        if not course_assignments or assign_idx >= len(course_assignments):
            continue

        assignment = course_assignments[assign_idx]

        # Ensure max_points is set on the assignment
        max_val = entry["max_grade"]
        if not assignment.max_points:
            assignment.max_points = max_val

        grade_val = entry["grade"]
        days_ago = entry.get("days_ago", 0)
        recorded_at = now - timedelta(days=days_ago)
        percentage = round((grade_val / max_val) * 100, 2)

        # Create GradeRecord (analytics source of truth)
        gr = GradeRecord(
            student_id=student.id,
            course_id=course.id,
            assignment_id=assignment.id,
            grade=grade_val,
            max_grade=max_val,
            percentage=percentage,
            source="seed",
            recorded_at=recorded_at,
        )
        db.add(gr)

        # Also create StudentAssignment for consistency
        sa = StudentAssignment(
            student_id=student.id,
            assignment_id=assignment.id,
            grade=grade_val,
            status="graded",
            submitted_at=recorded_at,
        )
        db.add(sa)
        count += 1

    db.commit()
    logger.info(f"Seeded {count} GradeRecord + StudentAssignment rows for student {student.id}")
    return count
