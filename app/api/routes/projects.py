"""Projects API routes.

Routes:
  GET    /api/projects/                                              — list user's active projects with milestones
  POST   /api/projects/                                             — create project
  PATCH  /api/projects/{id}                                         — update project
  DELETE /api/projects/{id}                                         — archive project
  POST   /api/projects/{id}/milestones                              — add milestone
  PATCH  /api/projects/{id}/milestones/{milestone_id}               — update/complete milestone
  DELETE /api/projects/{id}/milestones/{milestone_id}               — delete milestone
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app.db.database import get_db
from app.api.deps import get_current_user, require_feature
from app.models.user import User, UserRole
from app.models.project import Project, ProjectMilestone
from app.models.student import Student, parent_students

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["Projects"])

VALID_STATUSES = {"active", "completed", "archived"}
VALID_COLORS = {"blue", "green", "yellow", "pink", "purple", "orange", "red"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    course_id: Optional[int] = None
    student_id: Optional[int] = None
    due_date: Optional[str] = None  # ISO date string YYYY-MM-DD
    status: Optional[str] = "active"
    color: Optional[str] = "blue"


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    course_id: Optional[int] = None
    student_id: Optional[int] = None
    due_date: Optional[str] = None
    status: Optional[str] = None
    color: Optional[str] = None


class MilestoneCreate(BaseModel):
    title: str
    due_date: Optional[str] = None  # ISO date string YYYY-MM-DD
    order_index: Optional[int] = 0


class MilestoneUpdate(BaseModel):
    title: Optional[str] = None
    due_date: Optional[str] = None
    is_completed: Optional[bool] = None
    order_index: Optional[int] = None


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_milestone(m: ProjectMilestone) -> dict:
    return {
        "id": m.id,
        "project_id": m.project_id,
        "title": m.title,
        "due_date": m.due_date.isoformat() if m.due_date else None,
        "is_completed": m.is_completed or False,
        "completed_at": m.completed_at.isoformat() if m.completed_at else None,
        "order_index": m.order_index or 0,
    }


def _serialize_project(project: Project) -> dict:
    milestones = sorted(project.milestones, key=lambda m: m.order_index or 0)
    total = len(milestones)
    completed = sum(1 for m in milestones if m.is_completed)
    return {
        "id": project.id,
        "user_id": project.user_id,
        "student_id": project.student_id,
        "course_id": project.course_id,
        "course_name": project.course.name if project.course else None,
        "title": project.title,
        "description": project.description,
        "due_date": project.due_date.isoformat() if project.due_date else None,
        "status": project.status or "active",
        "color": project.color or "blue",
        "milestones": [_serialize_milestone(m) for m in milestones],
        "milestone_total": total,
        "milestone_completed": completed,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Authorization helper
# ---------------------------------------------------------------------------

def _assert_project_ownership(project: Project, current_user: User, db: Session):
    """Raise 404/403 if the user does not own the project."""
    if project.user_id != current_user.id:
        # Parents may also access projects they created for their children
        raise HTTPException(status_code=403, detail="Not authorized to access this project")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/")
def list_projects(
    _flag=Depends(require_feature("notes_projects")),
    student_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List user's projects (non-archived by default), eager-loading milestones."""
    q = (
        db.query(Project)
        .options(selectinload(Project.milestones), selectinload(Project.course))
        .filter(Project.user_id == current_user.id)
    )

    if status:
        if status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail=f"Invalid status. Use: {', '.join(sorted(VALID_STATUSES))}")
        q = q.filter(Project.status == status)
    else:
        q = q.filter(Project.status != "archived")

    if student_id is not None:
        q = q.filter(Project.student_id == student_id)

    projects = q.order_by(Project.updated_at.desc()).all()
    return [_serialize_project(p) for p in projects]


@router.post("/", status_code=201)
def create_project(
    payload: ProjectCreate,
    _flag=Depends(require_feature("notes_projects")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.color and payload.color not in VALID_COLORS:
        raise HTTPException(status_code=400, detail=f"Invalid color. Use: {', '.join(sorted(VALID_COLORS))}")
    if payload.status and payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use: {', '.join(sorted(VALID_STATUSES))}")

    from datetime import date
    due = None
    if payload.due_date:
        try:
            due = date.fromisoformat(payload.due_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due_date format. Use YYYY-MM-DD")

    project = Project(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        course_id=payload.course_id,
        student_id=payload.student_id,
        due_date=due,
        status=payload.status or "active",
        color=payload.color or "blue",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    # Re-query with relationships
    project = db.query(Project).options(selectinload(Project.milestones), selectinload(Project.course)).filter(Project.id == project.id).first()
    return _serialize_project(project)


@router.patch("/{project_id}")
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    _flag=Depends(require_feature("notes_projects")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = (
        db.query(Project)
        .options(selectinload(Project.milestones), selectinload(Project.course))
        .filter(Project.id == project_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _assert_project_ownership(project, current_user, db)

    if payload.color is not None and payload.color not in VALID_COLORS:
        raise HTTPException(status_code=400, detail=f"Invalid color. Use: {', '.join(sorted(VALID_COLORS))}")
    if payload.status is not None and payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use: {', '.join(sorted(VALID_STATUSES))}")

    from datetime import date
    update_data = payload.model_dump(exclude_unset=True)
    if "due_date" in update_data:
        raw = update_data.pop("due_date")
        if raw:
            try:
                update_data["due_date"] = date.fromisoformat(raw)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid due_date format. Use YYYY-MM-DD")
        else:
            update_data["due_date"] = None

    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    project = db.query(Project).options(selectinload(Project.milestones), selectinload(Project.course)).filter(Project.id == project_id).first()
    return _serialize_project(project)


@router.delete("/{project_id}", status_code=204)
def archive_project(
    project_id: int,
    _flag=Depends(require_feature("notes_projects")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _assert_project_ownership(project, current_user, db)

    project.status = "archived"
    db.commit()


# ---------------------------------------------------------------------------
# Milestone sub-routes
# ---------------------------------------------------------------------------

@router.post("/{project_id}/milestones", status_code=201)
def add_milestone(
    project_id: int,
    payload: MilestoneCreate,
    _flag=Depends(require_feature("notes_projects")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _assert_project_ownership(project, current_user, db)

    from datetime import date
    due = None
    if payload.due_date:
        try:
            due = date.fromisoformat(payload.due_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due_date format. Use YYYY-MM-DD")

    milestone = ProjectMilestone(
        project_id=project_id,
        title=payload.title,
        due_date=due,
        order_index=payload.order_index or 0,
        is_completed=False,
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return _serialize_milestone(milestone)


@router.patch("/{project_id}/milestones/{milestone_id}")
def update_milestone(
    project_id: int,
    milestone_id: int,
    payload: MilestoneUpdate,
    _flag=Depends(require_feature("notes_projects")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _assert_project_ownership(project, current_user, db)

    milestone = db.query(ProjectMilestone).filter(
        ProjectMilestone.id == milestone_id,
        ProjectMilestone.project_id == project_id,
    ).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")

    from datetime import date
    update_data = payload.model_dump(exclude_unset=True)
    if "due_date" in update_data:
        raw = update_data.pop("due_date")
        if raw:
            try:
                update_data["due_date"] = date.fromisoformat(raw)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid due_date format. Use YYYY-MM-DD")
        else:
            update_data["due_date"] = None

    # Track completion timestamp
    if "is_completed" in update_data:
        if update_data["is_completed"] and not milestone.is_completed:
            update_data["completed_at"] = datetime.now(timezone.utc)
        elif not update_data["is_completed"]:
            update_data["completed_at"] = None

    for field, value in update_data.items():
        setattr(milestone, field, value)

    db.commit()
    db.refresh(milestone)
    return _serialize_milestone(milestone)


@router.delete("/{project_id}/milestones/{milestone_id}", status_code=204)
def delete_milestone(
    project_id: int,
    milestone_id: int,
    _flag=Depends(require_feature("notes_projects")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    _assert_project_ownership(project, current_user, db)

    milestone = db.query(ProjectMilestone).filter(
        ProjectMilestone.id == milestone_id,
        ProjectMilestone.project_id == project_id,
    ).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")

    db.delete(milestone)
    db.commit()
