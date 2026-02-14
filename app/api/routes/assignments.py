from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.assignment import Assignment
from app.models.course import Course, student_courses
from app.models.notification import Notification, NotificationType
from app.models.student import Student, parent_students
from app.models.teacher import Teacher
from app.models.user import User, UserRole
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate, AssignmentResponse
from app.api.deps import get_current_user, can_access_course

router = APIRouter(prefix="/assignments", tags=["Assignments"])


def _get_accessible_course_ids(db: Session, user: User) -> list[int] | None:
    """Return course IDs accessible to the user, or None for admin (all access)."""
    if user.role == UserRole.ADMIN:
        return None  # Admin can see all

    ids: set[int] = set()

    # Courses created by the user
    created = db.query(Course.id).filter(Course.created_by_user_id == user.id).all()
    ids.update(r[0] for r in created)

    # Public courses
    public = db.query(Course.id).filter(Course.is_private == False).all()  # noqa: E712
    ids.update(r[0] for r in public)

    if user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if teacher:
            taught = db.query(Course.id).filter(Course.teacher_id == teacher.id).all()
            ids.update(r[0] for r in taught)

    elif user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if student:
            ids.update(c.id for c in student.courses)

    elif user.role == UserRole.PARENT:
        child_sids = [
            r[0] for r in db.query(parent_students.c.student_id).filter(
                parent_students.c.parent_id == user.id
            ).all()
        ]
        if child_sids:
            enrolled = db.query(student_courses.c.course_id).filter(
                student_courses.c.student_id.in_(child_sids)
            ).all()
            ids.update(r[0] for r in enrolled)

    return list(ids)


def _require_course_write(db: Session, user: User, course_id: int) -> Course:
    """Verify the user can write assignments to the course. Returns the course."""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if user.has_role(UserRole.ADMIN):
        return course

    if course.created_by_user_id == user.id:
        return course

    if user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if teacher and course.teacher_id == teacher.id:
            return course

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the course teacher or creator can manage assignments",
    )


def _notify_enrolled_students(db: Session, course: Course, assignment: Assignment, actor_name: str):
    """Send in-app notification to all enrolled students."""
    enrolled_user_ids = (
        db.query(Student.user_id)
        .join(student_courses, Student.id == student_courses.c.student_id)
        .filter(student_courses.c.course_id == course.id)
        .all()
    )
    for (uid,) in enrolled_user_ids:
        db.add(Notification(
            user_id=uid,
            type=NotificationType.ASSIGNMENT_DUE,
            title=f"New assignment in {course.name}",
            content=f"{actor_name} posted \"{assignment.title}\"",
            link=f"/courses/{course.id}",
        ))


def _to_response(assignment: Assignment) -> dict:
    """Convert assignment to response dict with course_name."""
    return {
        "id": assignment.id,
        "title": assignment.title,
        "description": assignment.description,
        "course_id": assignment.course_id,
        "course_name": assignment.course.name if assignment.course else None,
        "google_classroom_id": assignment.google_classroom_id,
        "due_date": assignment.due_date,
        "max_points": assignment.max_points,
        "created_at": assignment.created_at,
    }


@router.post("/", response_model=AssignmentResponse)
def create_assignment(
    assignment_data: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an assignment. Must have write access to the course."""
    course = _require_course_write(db, current_user, assignment_data.course_id)

    assignment = Assignment(**assignment_data.model_dump())
    db.add(assignment)
    db.flush()

    _notify_enrolled_students(db, course, assignment, current_user.full_name)
    db.commit()
    db.refresh(assignment)
    return _to_response(assignment)


@router.put("/{assignment_id}", response_model=AssignmentResponse)
def update_assignment(
    assignment_id: int,
    data: AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an assignment."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    _require_course_write(db, current_user, assignment.course_id)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(assignment, key, value)

    db.commit()
    db.refresh(assignment)
    return _to_response(assignment)


@router.delete("/{assignment_id}", status_code=status.HTTP_200_OK)
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an assignment."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    _require_course_write(db, current_user, assignment.course_id)

    db.delete(assignment)
    db.commit()
    return {"detail": "Assignment deleted"}


@router.get("/", response_model=list[AssignmentResponse])
def list_assignments(
    course_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List assignments scoped to accessible courses."""
    query = db.query(Assignment)

    if course_id:
        if not can_access_course(db, current_user, course_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")
        query = query.filter(Assignment.course_id == course_id)
    else:
        accessible = _get_accessible_course_ids(db, current_user)
        if accessible is not None:  # None means admin (all access)
            query = query.filter(Assignment.course_id.in_(accessible))

    assignments = query.order_by(Assignment.due_date.asc().nullslast(), Assignment.created_at.desc()).all()
    return [_to_response(a) for a in assignments]


@router.get("/{assignment_id}", response_model=AssignmentResponse)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get an assignment. Must have access to its course."""
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")

    if not can_access_course(db, current_user, assignment.course_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No access to this course")

    return _to_response(assignment)
