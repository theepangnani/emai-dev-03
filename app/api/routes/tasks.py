from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.models.user import User, UserRole
from app.models.task import Task
from app.models.student import parent_students
from app.api.deps import require_role
from app.schemas.task import TaskCreate, TaskUpdate, TaskResponse

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def _verify_student_link(db: Session, parent_id: int, student_id: int):
    """Verify parent has a link to the given student."""
    link = (
        db.query(parent_students)
        .filter(
            parent_students.c.parent_id == parent_id,
            parent_students.c.student_id == student_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Student not linked to your account")


@router.get("/", response_model=list[TaskResponse])
def list_tasks(
    student_id: Optional[int] = Query(None),
    is_completed: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """List tasks created by the current parent, optionally filtered."""
    query = db.query(Task).filter(Task.parent_id == current_user.id)

    if student_id is not None:
        query = query.filter(Task.student_id == student_id)
    if is_completed is not None:
        query = query.filter(Task.is_completed == is_completed)

    return query.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).all()


@router.post("/", response_model=TaskResponse, status_code=201)
def create_task(
    request: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Create a new task for a child (or unassigned)."""
    if request.student_id:
        _verify_student_link(db, current_user.id, request.student_id)

    task = Task(
        parent_id=current_user.id,
        student_id=request.student_id,
        title=request.title,
        description=request.description,
        due_date=request.due_date,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    request: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Update a task. Automatically sets completed_at when marking complete."""
    task = db.query(Task).filter(Task.id == task_id, Task.parent_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if request.student_id is not None:
        _verify_student_link(db, current_user.id, request.student_id)
        task.student_id = request.student_id

    if request.title is not None:
        task.title = request.title
    if request.description is not None:
        task.description = request.description
    if request.due_date is not None:
        task.due_date = request.due_date
    if request.is_completed is not None:
        task.is_completed = request.is_completed
        task.completed_at = datetime.utcnow() if request.is_completed else None

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Delete a task."""
    task = db.query(Task).filter(Task.id == task_id, Task.parent_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
