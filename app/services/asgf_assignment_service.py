"""ASGF Assignment Service — course auto-detection and role-aware assignment."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.models.course import Course, student_courses
from app.models.student import Student, parent_students

logger = get_logger(__name__)


def _keyword_confidence(topic: str, subject: str, course_name: str) -> float:
    """Score how well topic/subject match a course name using keyword matching.

    Returns:
        0.95 for exact subject match in course name,
        0.75 for partial match,
        0.3 for no match.
    """
    course_lower = course_name.lower()
    subject_lower = subject.lower().strip()
    topic_lower = topic.lower().strip()

    # Exact subject match in course name
    if subject_lower and subject_lower in course_lower:
        return 0.95

    # Check common subject aliases
    aliases: dict[str, list[str]] = {
        "math": ["mathematics", "calculus", "algebra", "geometry", "stats", "statistics"],
        "science": ["biology", "chemistry", "physics", "environmental"],
        "english": ["language arts", "literature", "writing", "ela"],
        "history": ["social studies", "civics", "geography", "world studies"],
        "french": ["fsl", "core french", "french immersion"],
    }
    for canonical, variants in aliases.items():
        subject_matches = subject_lower == canonical or subject_lower in variants
        course_matches = canonical in course_lower or any(v in course_lower for v in variants)
        if subject_matches and course_matches:
            return 0.95

    # Partial match: topic keywords in course name
    if topic_lower:
        topic_words = [w for w in topic_lower.split() if len(w) > 2]
        if topic_words:
            matches = sum(1 for w in topic_words if w in course_lower)
            if matches / len(topic_words) >= 0.5:
                return 0.75

    return 0.3


async def detect_course(
    topic: str,
    subject: str,
    student_id: int,
    db: Session,
) -> dict:
    """Match session topic to student's Google Classroom courses.

    Returns: { course_id, course_name, confidence }
    If confidence >= 0.85: auto-tag silently
    If confidence < 0.85: return options for user to confirm
    """
    # Get student's enrolled courses
    courses = (
        db.query(Course)
        .join(student_courses, student_courses.c.course_id == Course.id)
        .filter(student_courses.c.student_id == student_id)
        .all()
    )

    if not courses:
        return {"course_id": None, "course_name": None, "confidence": 0.0}

    best_match: dict = {"course_id": None, "course_name": None, "confidence": 0.0}

    for course in courses:
        conf = _keyword_confidence(topic, subject, course.name)
        if conf > best_match["confidence"]:
            best_match = {
                "course_id": str(course.id),
                "course_name": course.name,
                "confidence": conf,
            }

    logger.info(
        "ASGF course detection: student=%d, subject=%s, best=%s (%.2f)",
        student_id,
        subject,
        best_match["course_name"],
        best_match["confidence"],
    )

    return best_match


async def assign_material(
    material_id: int,
    assignment_type: str,
    course_id: int | None,
    due_date: str | None,
    db: Session,
) -> dict:
    """Assign the saved material based on user choice.

    assignment_type: "private", "share_teacher", "review_task",
                     "keep_personal", "share_parent", "submit_teacher"
    """
    from app.models.learning_history import LearningHistory

    # Find the learning history row by material_id
    history_row = (
        db.query(LearningHistory)
        .filter(LearningHistory.material_id == material_id)
        .first()
    )

    if not history_row:
        return {"success": False, "message": "Material not found"}

    # Apply assignment based on type
    if assignment_type in ("share_teacher", "submit_teacher"):
        history_row.teacher_visible = True

    if course_id:
        history_row.assigned_to_course = str(course_id)

    try:
        db.commit()
        logger.info(
            "ASGF assignment: material=%d, type=%s, course=%s",
            material_id,
            assignment_type,
            course_id,
        )
        return {"success": True, "message": f"Material assigned as '{assignment_type}'"}
    except Exception:
        db.rollback()
        logger.exception("ASGF assignment failed: material=%d", material_id)
        return {"success": False, "message": "Failed to assign material"}


def get_role_options(role: str) -> list[dict]:
    """Return assignment options based on user role."""
    if role == "parent":
        return [
            {
                "key": "private",
                "label": "Keep Private",
                "description": "Save for personal reference only",
            },
            {
                "key": "share_teacher",
                "label": "Share with Teacher",
                "description": "Make visible to the course teacher",
            },
            {
                "key": "review_task",
                "label": "Assign as Review Task",
                "description": "Create a review task with an optional due date",
            },
        ]
    elif role == "student":
        return [
            {
                "key": "keep_personal",
                "label": "Keep Personal",
                "description": "Save for your own study use",
            },
            {
                "key": "share_parent",
                "label": "Share with Parent",
                "description": "Let your parent see this material",
            },
            {
                "key": "submit_teacher",
                "label": "Submit to Teacher",
                "description": "Submit to your course teacher for review",
            },
        ]
    else:
        return [
            {
                "key": "private",
                "label": "Keep Private",
                "description": "Save for personal reference only",
            },
        ]


def resolve_student_id(
    user_id: int,
    role: str,
    child_id: int | None,
    db: Session,
) -> int | None:
    """Resolve the student_id for course detection."""
    if role == "student":
        student = db.query(Student).filter(Student.user_id == user_id).first()
        return student.id if student else None
    elif role == "parent" and child_id:
        # Verify parent-child relationship
        exists = (
            db.query(Student.id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(
                parent_students.c.parent_id == user_id,
                Student.id == child_id,
            )
            .first()
        )
        return exists[0] if exists else None
    elif role == "parent":
        # Use first linked child
        first = (
            db.query(Student.id)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(parent_students.c.parent_id == user_id)
            .first()
        )
        return first[0] if first else None
    return None
