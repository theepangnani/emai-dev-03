from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.models.user import User, UserRole
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.task import Task
from app.models.student import Student, parent_students
from app.models.course import Course, student_courses
from app.models.teacher import Teacher
from app.models.course_content import CourseContent
from app.models.study_guide import StudyGuide
from app.api.deps import get_current_user
from app.models.notification import Notification, NotificationType
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from app.services.audit_service import log_action
from app.services.notification_service import notify_parents_of_student
from app.domains.tasks.services import TaskService

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




def _task_eager_options():
    """SQLAlchemy options to eager-load Task relationships (avoids N+1)."""
    return [
        selectinload(Task.creator),
        selectinload(Task.assignee),
        selectinload(Task.course),
        selectinload(Task.course_content),
        selectinload(Task.study_guide),
        selectinload(Task.note),
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
        "note_id": task.note_id,
        "course_name": task.course.name if task.course else None,
        "course_content_title": task.course_content.title if task.course_content else None,
        "study_guide_title": task.study_guide.title if task.study_guide else None,
        "study_guide_type": task.study_guide.guide_type if task.study_guide else None,
        "last_reminder_sent_at": task.last_reminder_sent_at,
        # CB-TASKSYNC-001 (#3920) — source attribution surfaced for frontend badges
        # and calendar FK-style dedup (source + source_ref).
        "source": task.source,
        "source_ref": task.source_ref,
        "source_confidence": task.source_confidence,
        "source_status": task.source_status,
        "source_created_at": task.source_created_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


@router.get("/assignable-users")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_assignable_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get users that the current user can assign tasks to."""
    task_service = TaskService(db)
    return task_service.get_assignable_users(current_user)


@router.get("/", response_model=list[TaskResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_tasks(
    request: Request,
    assigned_to_user_id: Optional[int] = Query(None),
    is_completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    include_archived: bool = Query(False),
    course_id: Optional[int] = Query(None),
    study_guide_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tasks where the current user is creator OR assignee (parents also see children's tasks)."""
    filters = [
        Task.created_by_user_id == current_user.id,
        Task.assigned_to_user_id == current_user.id,
    ]

    # Parents also see tasks assigned to their linked children
    if current_user.role == UserRole.PARENT:
        child_student_ids = [
            r[0] for r in db.query(parent_students.c.student_id)
            .filter(parent_students.c.parent_id == current_user.id).all()
        ]
        if child_student_ids:
            child_user_ids = [
                r[0] for r in db.query(Student.user_id)
                .filter(Student.id.in_(child_student_ids)).all()
            ]
            if child_user_ids:
                filters.append(Task.assigned_to_user_id.in_(child_user_ids))

    query = db.query(Task).options(*_task_eager_options()).filter(or_(*filters))

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
    if study_guide_id is not None:
        query = query.filter(Task.study_guide_id == study_guide_id)

    # Portable NULL handling across DB backends: non-null due dates first, nulls last.
    tasks = query.order_by(
        Task.due_date.is_(None).asc(),
        Task.due_date.asc(),
        Task.created_at.desc(),
    ).all()
    return [_task_to_response(t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_task(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single task by ID. Only accessible to creator or assignee."""
    task = db.query(Task).options(*_task_eager_options()).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task_service = TaskService(db)
    if not task_service.can_view_task(task, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view this task")

    return _task_to_response(task)


@router.post("/", response_model=TaskResponse, status_code=201)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def create_task(
    request: Request,
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new task, optionally assigned to another user."""
    task_service = TaskService(db)
    if data.assigned_to_user_id:
        task_service.validate_assignment_relationship(current_user, data.assigned_to_user_id)

    # Resolve legacy student_id from assigned_to_user_id for backwards compat
    legacy_student_id = None
    if data.assigned_to_user_id:
        student = db.query(Student).filter(Student.user_id == data.assigned_to_user_id).first()
        if student:
            legacy_student_id = student.id

    task = Task(
        created_by_user_id=current_user.id,
        assigned_to_user_id=data.assigned_to_user_id,
        parent_id=current_user.id,  # Legacy column — existing DB has NOT NULL constraint
        student_id=legacy_student_id,  # Legacy column
        title=data.title,
        description=data.description,
        due_date=data.due_date,
        priority=_normalize_priority(data.priority) or "medium",
        category=data.category,
        course_id=data.course_id,
        course_content_id=data.course_content_id,
        study_guide_id=data.study_guide_id,
    )
    db.add(task)
    db.flush()
    log_action(db, user_id=current_user.id, action="create", resource_type="task", resource_id=task.id,
               details={"title": data.title, "assigned_to": data.assigned_to_user_id})
    db.commit()
    task = db.query(Task).options(*_task_eager_options()).filter(Task.id == task.id).first()

    # Notify parents if a student created a task
    if current_user.role == UserRole.STUDENT:
        try:
            notify_parents_of_student(
                db=db,
                student_user=current_user,
                title=f"New task: {task.title}",
                content=f"{current_user.full_name} created task \"{task.title}\".",
                notification_type=NotificationType.TASK_DUE,
                link=f"/tasks/{task.id}",
                source_type="task",
                source_id=task.id,
            )
        except Exception:
            pass  # Never break primary action

    return _task_to_response(task)


@router.patch("/{task_id}", response_model=TaskResponse)
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def update_task(
    request: Request,
    task_id: int,
    data: TaskUpdate,
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

    task_service = TaskService(db)

    # Assignees can only toggle completion
    if not is_creator:
        if data.is_completed is not None:
            task_service.toggle_completion(task, current_user, data.is_completed)
            db.commit()
            task = db.query(Task).options(*_task_eager_options()).filter(Task.id == task.id).first()

            # CB-CMCP-001 M3-D 3D-2 (#4659) — award XP when a student
            # completes an artifact assigned via 3D-1's fan-out. Best-effort
            # try/except so an XP-side failure never breaks the Task PATCH.
            if (
                data.is_completed
                and current_user.role == UserRole.STUDENT
                and task.source == "cmcp_artifact"
                and task.study_guide_id is not None
            ):
                try:
                    from app.services.cmcp.xp_eligibility import (
                        award_xp_for_completed_artifact,
                    )

                    award_xp_for_completed_artifact(
                        artifact_id=task.study_guide_id,
                        student_user_id=current_user.id,
                        task_source=task.source,
                        db=db,
                    )
                except Exception:
                    pass  # Never break primary action

            # Notify the task creator (parent) when assignee completes the task
            if data.is_completed and task.created_by_user_id and task.created_by_user_id != current_user.id:
                try:
                    creator = db.query(User).filter(User.id == task.created_by_user_id).first()
                    if creator:
                        notification = Notification(
                            user_id=creator.id,
                            type=NotificationType.TASK_DUE,
                            title=f"{current_user.full_name} completed \"{task.title}\"",
                            content=f"{current_user.full_name} has completed the task \"{task.title}\".",
                            link=f"/tasks/{task.id}",
                            source_type="task",
                            source_id=task.id,
                        )
                        db.add(notification)
                        db.commit()
                except Exception:
                    pass  # Never break primary action

            return _task_to_response(task)
        else:
            raise HTTPException(status_code=403, detail="Only the task creator can edit task details")

    # Creator can update all fields
    if data.assigned_to_user_id is not None:
        if data.assigned_to_user_id == 0:
            # Convention: 0 means unassign
            task.assigned_to_user_id = None
        else:
            task_service.validate_assignment_relationship(current_user, data.assigned_to_user_id)
            task.assigned_to_user_id = data.assigned_to_user_id

    if data.title is not None:
        task.title = data.title
    if data.description is not None:
        task.description = data.description
    if data.due_date is not None:
        task.due_date = data.due_date
    if data.is_completed is not None:
        task_service.toggle_completion(task, current_user, data.is_completed)
    if data.priority is not None:
        task.priority = _normalize_priority(data.priority)
    if data.category is not None:
        task.category = data.category
    if data.course_id is not None:
        task.course_id = data.course_id if data.course_id != 0 else None
    if data.course_content_id is not None:
        task.course_content_id = data.course_content_id if data.course_content_id != 0 else None
    if data.study_guide_id is not None:
        task.study_guide_id = data.study_guide_id if data.study_guide_id != 0 else None

    db.commit()
    task = db.query(Task).options(*_task_eager_options()).filter(Task.id == task.id).first()
    return _task_to_response(task)


@router.delete("/{task_id}", status_code=204)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_task(
    request: Request,
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

    task_service = TaskService(db)
    task_service.archive_task(task, current_user)
    log_action(db, user_id=current_user.id, action="delete", resource_type="task", resource_id=task.id,
               details={"title": task.title})
    db.commit()


@router.patch("/{task_id}/restore", response_model=TaskResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def restore_task(
    request: Request,
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

    task_service = TaskService(db)
    task_service.restore_task(task, current_user)
    db.commit()
    task = db.query(Task).options(*_task_eager_options()).filter(Task.id == task.id).first()
    return _task_to_response(task)


@router.delete("/{task_id}/permanent", status_code=204)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def permanent_delete_task(
    request: Request,
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


@router.post("/{task_id}/remind")
@limiter.limit("20/minute", key_func=get_user_id_or_ip)
def send_task_reminder(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a reminder notification for a task to the assigned student.

    - Only the task creator (parent) can send reminders
    - Task must be assigned to someone and not completed
    - Rate limited: 1 reminder per task per 24 hours
    """
    task = db.query(Task).options(*_task_eager_options()).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Only the creator can send reminders
    if task.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the task creator can send reminders")

    # Task must be assigned to someone
    if not task.assigned_to_user_id:
        raise HTTPException(status_code=400, detail="Task is not assigned to anyone")

    # Task must not be completed
    if task.is_completed:
        raise HTTPException(status_code=400, detail="Task is already completed")

    # Rate limit: 1 reminder per 24 hours
    if task.last_reminder_sent_at:
        hours_since = (datetime.now(timezone.utc) - task.last_reminder_sent_at).total_seconds() / 3600
        if hours_since < 24:
            remaining = 24 - hours_since
            raise HTTPException(
                status_code=429,
                detail=f"Reminder already sent. Try again in {int(remaining)} hours."
            )

    # Determine due status for message
    now = datetime.now(timezone.utc)
    if task.due_date:
        if task.due_date.replace(tzinfo=timezone.utc) < now:
            due_status = "overdue"
        elif task.due_date.replace(tzinfo=timezone.utc).date() == now.date():
            due_status = "due today"
        else:
            due_status = "due soon"
    else:
        due_status = "pending"

    # Create in-app notification for the assigned student
    assignee = db.query(User).filter(User.id == task.assigned_to_user_id).first()
    if not assignee:
        raise HTTPException(status_code=400, detail="Assigned user not found")

    notification = Notification(
        user_id=assignee.id,
        type=NotificationType.TASK_DUE,
        title=f"Reminder: {task.title}",
        content=f"Reminder: {task.title} is {due_status}. Your parent would like you to complete it.",
        link=f"/tasks/{task.id}",
        source_type="task",
        source_id=task.id,
    )
    db.add(notification)

    # Update last_reminder_sent_at
    reminded_at = datetime.now(timezone.utc)
    task.last_reminder_sent_at = reminded_at

    log_action(
        db, user_id=current_user.id, action="remind", resource_type="task",
        resource_id=task.id, details={"assignee_id": assignee.id, "title": task.title},
    )

    db.commit()

    return {
        "success": True,
        "reminded_at": reminded_at.isoformat(),
        "assignee_name": assignee.full_name,
    }
