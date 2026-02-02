import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import insert

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.student import Student, parent_students, RelationshipType
from app.models.course import Course, student_courses
from app.models.assignment import Assignment
from app.models.study_guide import StudyGuide
from app.api.deps import require_role
from app.schemas.parent import (
    ChildSummary, ChildOverview, LinkChildRequest,
    DiscoveredChild, DiscoverChildrenResponse, LinkChildrenBulkRequest,
)
from app.schemas.course import CourseResponse
from app.schemas.assignment import AssignmentResponse
from app.services.google_classroom import list_courses, list_course_students

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/parent", tags=["Parent"])


@router.get("/children", response_model=list[ChildSummary])
def list_children(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """List all children linked to the current parent."""
    rows = (
        db.query(Student, parent_students.c.relationship_type)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .filter(parent_students.c.parent_id == current_user.id)
        .all()
    )

    result = []
    for student, rel_type in rows:
        user = student.user
        result.append(ChildSummary(
            student_id=student.id,
            user_id=student.user_id,
            full_name=user.full_name if user else "Unknown",
            grade_level=student.grade_level,
            school_name=student.school_name,
            relationship_type=rel_type.value if rel_type else None,
        ))

    return result


@router.post("/children/link", response_model=ChildSummary)
def link_child(
    request: LinkChildRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Link a student to the current parent by the student's email."""
    # Find the student's user account
    student_user = (
        db.query(User)
        .filter(User.email == request.student_email, User.role == UserRole.STUDENT)
        .first()
    )
    if not student_user:
        raise HTTPException(status_code=404, detail="No student account found with that email")

    # Find or create the Student record
    student = db.query(Student).filter(Student.user_id == student_user.id).first()
    if not student:
        student = Student(user_id=student_user.id)
        db.add(student)
        db.flush()

    # Check if already linked to this parent
    existing_link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student.id,
        )
        .first()
    )
    if existing_link:
        raise HTTPException(status_code=400, detail="This student is already linked to your account")

    # Insert into join table
    rel_type = RelationshipType(request.relationship_type)
    db.execute(
        insert(parent_students).values(
            parent_id=current_user.id,
            student_id=student.id,
            relationship_type=rel_type,
        )
    )
    db.commit()

    return ChildSummary(
        student_id=student.id,
        user_id=student.user_id,
        full_name=student_user.full_name,
        grade_level=student.grade_level,
        school_name=student.school_name,
        relationship_type=rel_type.value,
    )


@router.post("/children/discover-google", response_model=DiscoverChildrenResponse)
def discover_children_google(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Discover children via Google Classroom courses."""
    if not current_user.google_access_token:
        return DiscoverChildrenResponse(discovered=[], google_connected=False, courses_searched=0)

    try:
        courses, credentials = list_courses(
            current_user.google_access_token,
            current_user.google_refresh_token,
        )
    except Exception as e:
        logger.warning(f"Failed to list Google courses for parent {current_user.id}: {e}")
        return DiscoverChildrenResponse(discovered=[], google_connected=True, courses_searched=0)

    # Update tokens if refreshed
    if credentials.token != current_user.google_access_token:
        current_user.google_access_token = credentials.token
        if credentials.refresh_token:
            current_user.google_refresh_token = credentials.refresh_token
        db.commit()

    # Collect student emails from all courses
    student_emails: dict[str, list[str]] = {}  # email -> list of course names
    for course in courses:
        course_id = course.get("id")
        course_name = course.get("name", "Unknown Course")
        if not course_id:
            continue
        try:
            students, credentials = list_course_students(
                current_user.google_access_token,
                course_id,
                current_user.google_refresh_token,
            )
            for s in students:
                profile = s.get("profile", {})
                email = profile.get("emailAddress", "").lower()
                if email:
                    student_emails.setdefault(email, []).append(course_name)
        except Exception as e:
            logger.warning(f"Failed to list students for course {course_id}: {e}")
            continue

    if not student_emails:
        return DiscoverChildrenResponse(discovered=[], google_connected=True, courses_searched=len(courses))

    # Match against local student users
    matched_users = (
        db.query(User)
        .filter(User.email.in_(list(student_emails.keys())), User.role == UserRole.STUDENT)
        .all()
    )

    discovered = []
    for user in matched_users:
        student = db.query(Student).filter(Student.user_id == user.id).first()
        already_linked = False
        if student:
            existing_link = (
                db.query(parent_students)
                .filter(
                    parent_students.c.parent_id == current_user.id,
                    parent_students.c.student_id == student.id,
                )
                .first()
            )
            already_linked = existing_link is not None

        discovered.append(DiscoveredChild(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            google_courses=student_emails.get(user.email.lower(), []),
            already_linked=already_linked,
        ))

    return DiscoverChildrenResponse(
        discovered=discovered,
        google_connected=True,
        courses_searched=len(courses),
    )


@router.post("/children/link-bulk", response_model=list[ChildSummary])
def link_children_bulk(
    request: LinkChildrenBulkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Link multiple students to the current parent."""
    rel_type = RelationshipType(request.relationship_type)
    linked = []
    for user_id in request.user_ids:
        student_user = (
            db.query(User)
            .filter(User.id == user_id, User.role == UserRole.STUDENT)
            .first()
        )
        if not student_user:
            continue

        student = db.query(Student).filter(Student.user_id == user_id).first()
        if not student:
            student = Student(user_id=user_id)
            db.add(student)
            db.flush()

        # Skip if already linked
        existing_link = (
            db.query(parent_students)
            .filter(
                parent_students.c.parent_id == current_user.id,
                parent_students.c.student_id == student.id,
            )
            .first()
        )
        if existing_link:
            continue

        db.execute(
            insert(parent_students).values(
                parent_id=current_user.id,
                student_id=student.id,
                relationship_type=rel_type,
            )
        )
        db.flush()

        linked.append(ChildSummary(
            student_id=student.id,
            user_id=student.user_id,
            full_name=student_user.full_name,
            grade_level=student.grade_level,
            school_name=student.school_name,
            relationship_type=rel_type.value,
        ))

    db.commit()
    return linked


@router.get("/children/{student_id}/overview", response_model=ChildOverview)
def get_child_overview(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Get detailed overview of a linked child's courses, assignments, and study materials."""
    # Verify parent-student link exists
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == current_user.id,
            parent_students.c.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Student not found or not linked to your account")

    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Get child's courses via student_courses join table
    courses = (
        db.query(Course)
        .join(student_courses, student_courses.c.course_id == Course.id)
        .filter(student_courses.c.student_id == student.id)
        .all()
    )

    # Get assignments for those courses
    course_ids = [c.id for c in courses]
    assignments = []
    if course_ids:
        assignments = (
            db.query(Assignment)
            .filter(Assignment.course_id.in_(course_ids))
            .order_by(Assignment.due_date.desc())
            .all()
        )

    # Count study guides for the child's user account
    study_guides_count = (
        db.query(StudyGuide)
        .filter(StudyGuide.user_id == student.user_id)
        .count()
    )

    user = student.user
    return ChildOverview(
        student_id=student.id,
        user_id=student.user_id,
        full_name=user.full_name if user else "Unknown",
        grade_level=student.grade_level,
        courses=courses,
        assignments=assignments,
        study_guides_count=study_guides_count,
    )
