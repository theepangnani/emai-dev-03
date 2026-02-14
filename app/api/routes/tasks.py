from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.task import Task
from app.models.student import Student, parent_students
from app.models.course import Course, student_courses
from app.models.teacher import Teacher
from app.models.course_content import CourseContent
from app.models.study_guide import StudyGuide
from app.api.deps import get_current_user
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.services.audit_service import log_action

router = APIRouter(prefix="/tasks", tags=["Tasks"])
VALID_PRIORITIES = {"low", "medium", "high"}


def _normalize_priority(priority: Optional[str]) -> Optional[str]:
    """Normalize and validate task priority values."""
    if priority is None:
        return None
    normalized = priority.strip().lower()
    if normalized not in VALID_PRIORITIES:
        raise HTTPException(status_code=400, detail="Invalid priority. Use: low, medium, high")
    return normalized


def _verify_assignment_relationship(db: Session, creator: User, assigned_to_user_id: int):
    """Verify the creator has a valid relationship with the assignee."""
    assignee = db.query(User).filter(User.id == assigned_to_user_id).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="Assigned user not found")

    if creator.role == UserRole.PARENT:
        # Parent can assign to linked students
        link = (
            db.query(parent_students)
            .join(Student, Student.id == parent_students.c.student_id)
            .filter(
                parent_students.c.parent_id == creator.id,
                Student.user_id == assigned_to_user_id,
            )
            .first()
        )
        if not link:
            raise HTTPException(status_code=403, detail="You can only assign tasks to your linked children")

    elif creator.role == UserRole.TEACHER:
        # Teacher can assign to students in their courses
        teacher = db.query(Teacher).filter(Teacher.user_id == creator.id).first()
        if not teacher:
            raise HTTPException(status_code=403, detail="Teacher profile not found")
        student = db.query(Student).filter(Student.user_id == assigned_to_user_id).first()
        if not student:
            raise HTTPException(status_code=403, detail="Assigned user is not a student")
        # Check student is enrolled in one of teacher's courses
        link = (
            db.query(student_courses)
            .join(Course, Course.id == student_courses.c.course_id)
            .filter(
                Course.teacher_id == teacher.id,
                student_courses.c.student_id == student.id,
            )
            .first()
        )
        if not link:
            raise HTTPException(status_code=403, detail="Student is not enrolled in any of your courses")

    elif creator.role == UserRole.STUDENT:
        # Student can assign to linked parents
        student = db.query(Student).filter(Student.user_id == creator.id).first()
        if not student:
            raise HTTPException(status_code=403, detail="Student profile not found")
        link = (
            db.query(parent_students)
            .filter(
                parent_students.c.student_id == student.id,
                parent_students.c.parent_id == assigned_to_user_id,
            )
            .first()
        )
        if not link:
            raise HTTPException(status_code=403, detail="You can only assign tasks to your linked parents")

    else:
        # Admin can only create personal tasks
        raise HTTPException(status_code=403, detail="You can only create personal tasks")


def _task_eager_options():
    """SQLAlchemy options to eager-load Task relationships (avoids N+1)."""
    return [
        selectinload(Task.creator),
        selectinload(Task.assignee),
        selectinload(Task.course),
        selectinload(Task.course_content),
        selectinload(Task.study_guide),
    ]


def _task_to_response(task: Task) -> dict:
    """Convert a Task ORM object to a response dict with creator/assignee names.

    Expects relationships to be eager-loaded via _task_eager_options().
    """
    raw_priority = task.priority
    if hasattr(raw_priority, "value"):  # Backwards compat if ORM returns enum-like values
        raw_priority = raw_priority.value
    normalized_priority = str(raw_priority).lower() if raw_priority else "medium"
    if normalized_priority not in VALID_PRIORITIES:
        normalized_priority = "medium"

    return {
        "id": task.id,
        "created_by_user_id": task.created_by_user_id,
        "assigned_to_user_id": task.assigned_to_user_id,
        "title": task.title,
        "description": task.description,
        "due_date": task.due_date,
        "is_completed": task.is_completed,
        "completed_at": task.completed_at,
        "archived_at": task.archived_at,
        "priority": normalized_priority,
        "category": task.category,
        "creator_name": task.creator.full_name if task.creator else "Unknown",
        "assignee_name": task.assignee.full_name if task.assignee else None,
        "course_id": task.course_id,
        "course_content_id": task.course_content_id,
        "study_guide_id": task.study_guide_id,
        "course_name": task.course.name if task.course else None,
        "course_content_title": task.course_content.title if task.course_content else None,
        "study_guide_title": task.study_guide.title if task.study_guide else None,
        "study_guide_type": task.study_guide.guide_type if task.study_guide else None,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


@router.get("/assignable-users")
def get_assignable_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get users that the current user can assign tasks to."""
    users = []

    if current_user.role == UserRole.PARENT:
        # Parent can assign to linked children
        rows = (
            db.query(Student, User)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .join(User, User.id == Student.user_id)
            .filter(parent_students.c.parent_id == current_user.id)
            .all()
        )
        for _, u in rows:
            users.append({"user_id": u.id, "name": u.full_name, "role": u.role.value})

    elif current_user.role == UserRole.TEACHER:
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if teacher:
            rows = (
                db.query(Student, User)
                .join(student_courses, student_courses.c.student_id == Student.id)
                .join(Course, Course.id == student_courses.c.course_id)
                .join(User, User.id == Student.user_id)
                .filter(Course.teacher_id == teacher.id)
                .distinct()
                .all()
            )
            for _, u in rows:
                users.append({"user_id": u.id, "name": u.full_name, "role": u.role.value})

    elif current_user.role == UserRole.STUDENT:
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if student:
            rows = (
                db.query(User)
                .join(parent_students, parent_students.c.parent_id == User.id)
                .filter(parent_students.c.student_id == student.id)
                .all()
            )
            for u in rows:
                users.append({"user_id": u.id, "name": u.full_name, "role": u.role.value})

    return users


@router.get("/", response_model=list[TaskResponse])
def list_tasks(
    assigned_to_user_id: Optional[int] = Query(None),
    is_completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    course_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tasks where the current user is creator OR assignee."""
    query = db.query(Task).options(*_task_eager_options()).filter(
        or_(
            Task.created_by_user_id == current_user.id,
            Task.assigned_to_user_id == current_user.id,
        )
    )

    # Exclude archived tasks by default
    if not include_archived:
        query = query.filter(Task.archived_at.is_(None))

    if assigned_to_user_id is not None:
        query = query.filter(Task.assigned_to_user_id == assigned_to_user_id)
    if is_completed is not None:
        query = query.filter(Task.is_completed == is_completed)
    if priority is not None:
        query = query.filter(Task.priority == _normalize_priority(priority))
    if course_id is not None:
        query = query.filter(Task.course_id == course_id)

    # Portable NULL handling across DB backends: non-null due dates first, nulls last.
    tasks = query.order_by(
        Task.due_date.is_(None).asc(),
        Task.due_date.asc(),
        Task.created_at.desc(),
    ).all()
    return [_task_to_response(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single task by ID. Only accessible to creator or assignee."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.created_by_user_id != current_user.id and task.assigned_to_user_id != current_user.id:
        # Parents can also view tasks assigned to their children
        if current_user.role == UserRole.PARENT:
            child_user_ids = [
                r[0] for r in db.query(Student.user_id)
                .join(parent_students, parent_students.c.student_id == Student.id)
                .filter(parent_students.c.parent_id == current_user.id)
                .all()
            ]
            if task.assigned_to_user_id not in child_user_ids and task.created_by_user_id not in child_user_ids:
                raise HTTPException(status_code=403, detail="Not authorized to view this task")
        else:
            raise HTTPException(status_code=403, detail="Not authorized to view this task")
    return _task_to_response(task)


@router.post("/", response_model=TaskResponse, status_code=201)
def create_task(
    request: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new task, optionally assigned to another user."""
    if request.assigned_to_user_id:
        _verify_assignment_relationship(db, current_user, request.assigned_to_user_id)

    # Resolve legacy student_id from assigned_to_user_id for backwards compat
    legacy_student_id = None
    if request.assigned_to_user_id:
        student = db.query(Student).filter(Student.user_id == request.assigned_to_user_id).first()
        if student:
            legacy_student_id = student.id

    task = Task(
        created_by_user_id=current_user.id,
        assigned_to_user_id=request.assigned_to_user_id,
        parent_id=current_user.id,  # Legacy column — existing DB has NOT NULL constraint
        student_id=legacy_student_id,  # Legacy column
        title=request.title,
        description=request.description,
        due_date=request.due_date,
        priority=_normalize_priority(request.priority) or "medium",
        category=request.category,
        course_id=request.course_id,
        course_content_id=request.course_content_id,
        study_guide_id=request.study_guide_id,
    )
    db.add(task)
    db.flush()
    log_action(db, user_id=current_user.id, action="create", resource_type="task", resource_id=task.id,
               details={"title": request.title, "assigned_to": request.assigned_to_user_id})
    db.commit()
    db.refresh(task)
    return _task_to_response(task)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    request: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a task. Only the creator can edit. Assignee can only toggle completion."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    is_creator = task.created_by_user_id == current_user.id
    is_assignee = task.assigned_to_user_id == current_user.id

    if not is_creator and not is_assignee:
        raise HTTPException(status_code=404, detail="Task not found")

    # Assignees can only toggle completion
    if not is_creator:
        if request.is_completed is not None:
            task.is_completed = request.is_completed
            task.completed_at = datetime.now(timezone.utc) if request.is_completed else None
            task.archived_at = datetime.now(timezone.utc) if request.is_completed else None
            db.commit()
            db.refresh(task)
            return _task_to_response(task)
        else:
            raise HTTPException(status_code=403, detail="Only the task creator can edit task details")

    # Creator can update all fields
    if request.assigned_to_user_id is not None:
        if request.assigned_to_user_id == 0:
            # Convention: 0 means unassign
            task.assigned_to_user_id = None
        else:
            _verify_assignment_relationship(db, current_user, request.assigned_to_user_id)
            task.assigned_to_user_id = request.assigned_to_user_id

    if request.title is not None:
        task.title = request.title
    if request.description is not None:
        task.description = request.description
    if request.due_date is not None:
        task.due_date = request.due_date
    if request.is_completed is not None:
        task.is_completed = request.is_completed
        task.completed_at = datetime.now(timezone.utc) if request.is_completed else None
        # Auto-archive on completion, un-archive on un-completion
        task.archived_at = datetime.now(timezone.utc) if request.is_completed else None
    if request.priority is not None:
        task.priority = _normalize_priority(request.priority)
    if request.category is not None:
        task.category = request.category
    if request.course_id is not None:
        task.course_id = request.course_id if request.course_id != 0 else None
    if request.course_content_id is not None:
        task.course_content_id = request.course_content_id if request.course_content_id != 0 else None
    if request.study_guide_id is not None:
        task.study_guide_id = request.study_guide_id if request.study_guide_id != 0 else None

    db.commit()
    db.refresh(task)
    return _task_to_response(task)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete (archive) a task. Only the creator can archive."""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.created_by_user_id == current_user.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.archived_at = datetime.now(timezone.utc)
    log_action(db, user_id=current_user.id, action="delete", resource_type="task", resource_id=task.id,
               details={"title": task.title})
    db.commit()


@router.patch("/{task_id}/restore", response_model=TaskResponse)
def restore_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Restore an archived task. Only the creator can restore."""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.created_by_user_id == current_user.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.archived_at:
        raise HTTPException(status_code=400, detail="Task is not archived")

    task.archived_at = None
    task.is_completed = False
    task.completed_at = None
    db.commit()
    db.refresh(task)
    return _task_to_response(task)


@router.delete("/{task_id}/permanent", status_code=204)
def permanent_delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete an archived task. Only the creator can permanently delete."""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.created_by_user_id == current_user.id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if not task.archived_at:
        raise HTTPException(status_code=400, detail="Task must be archived before permanent deletion")

    db.delete(task)
    db.commit()
