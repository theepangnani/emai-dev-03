"""API routes for student goals and milestones."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import User, UserRole
from app.schemas.student_goal import (
    AIMilestonesResponse,
    GoalMilestoneCreate,
    GoalMilestoneResponse,
    GoalMilestoneUpdate,
    GoalProgressUpdate,
    StudentGoalCreate,
    StudentGoalResponse,
    StudentGoalSummaryResponse,
    StudentGoalUpdate,
)
from app.services.student_goal import StudentGoalService

router = APIRouter(prefix="/goals", tags=["student-goals"])


def _svc(db: Session = Depends(get_db)) -> StudentGoalService:
    return StudentGoalService(db)


# ---------------------------------------------------------------------------
# Goal endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=StudentGoalResponse, status_code=201)
def create_goal(
    data: StudentGoalCreate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    svc: StudentGoalService = Depends(_svc),
):
    """Create a new goal for the authenticated student."""
    return svc.create_goal(current_user, data)


@router.get("/", response_model=List[StudentGoalSummaryResponse])
def list_goals(
    status: Optional[str] = Query(default=None, description="Filter by status"),
    category: Optional[str] = Query(default=None, description="Filter by category"),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    svc: StudentGoalService = Depends(_svc),
):
    """List all goals for the authenticated student."""
    goals = svc.list_goals(current_user, status_filter=status, category_filter=category)

    # Annotate with milestone counts
    result = []
    for goal in goals:
        summary = StudentGoalSummaryResponse.model_validate(goal)
        summary.milestone_count = len(goal.milestones)
        summary.completed_milestone_count = sum(1 for m in goal.milestones if m.completed)
        result.append(summary)
    return result


@router.get("/student/{student_id}", response_model=List[StudentGoalSummaryResponse])
def get_child_goals(
    student_id: int,
    status: Optional[str] = Query(default=None),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.ADMIN)),
    svc: StudentGoalService = Depends(_svc),
):
    """Parent: view a linked child's goals."""
    goals = svc.get_parent_child_goals(current_user, student_id, status_filter=status)
    result = []
    for goal in goals:
        summary = StudentGoalSummaryResponse.model_validate(goal)
        summary.milestone_count = len(goal.milestones)
        summary.completed_milestone_count = sum(1 for m in goal.milestones if m.completed)
        result.append(summary)
    return result


@router.get("/{goal_id}", response_model=StudentGoalResponse)
def get_goal(
    goal_id: int,
    current_user: User = Depends(get_current_user),
    svc: StudentGoalService = Depends(_svc),
):
    """Get a single goal with all milestones."""
    return svc.get_goal(goal_id, current_user)


@router.patch("/{goal_id}", response_model=StudentGoalResponse)
def update_goal(
    goal_id: int,
    data: StudentGoalUpdate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    svc: StudentGoalService = Depends(_svc),
):
    """Update goal metadata."""
    return svc.update_goal(goal_id, current_user, data)


@router.delete("/{goal_id}", status_code=204)
def delete_goal(
    goal_id: int,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    svc: StudentGoalService = Depends(_svc),
):
    """Delete a goal and all its milestones."""
    svc.delete_goal(goal_id, current_user)


# ---------------------------------------------------------------------------
# Progress update
# ---------------------------------------------------------------------------


@router.post("/{goal_id}/progress", response_model=StudentGoalResponse)
def update_progress(
    goal_id: int,
    data: GoalProgressUpdate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    svc: StudentGoalService = Depends(_svc),
):
    """Update the progress percentage of a goal."""
    return svc.update_progress(goal_id, current_user, data)


# ---------------------------------------------------------------------------
# Milestone endpoints
# ---------------------------------------------------------------------------


@router.post("/{goal_id}/milestones", response_model=GoalMilestoneResponse, status_code=201)
def add_milestone(
    goal_id: int,
    data: GoalMilestoneCreate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    svc: StudentGoalService = Depends(_svc),
):
    """Add a milestone to a goal."""
    return svc.add_milestone(goal_id, current_user, data)


@router.patch("/{goal_id}/milestones/{milestone_id}", response_model=GoalMilestoneResponse)
def update_milestone(
    goal_id: int,
    milestone_id: int,
    data: GoalMilestoneUpdate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    svc: StudentGoalService = Depends(_svc),
):
    """Update or complete a milestone."""
    return svc.update_milestone(goal_id, milestone_id, current_user, data)


# ---------------------------------------------------------------------------
# AI milestone generation
# ---------------------------------------------------------------------------


@router.post("/{goal_id}/ai-milestones", response_model=AIMilestonesResponse)
def generate_ai_milestones(
    goal_id: int,
    save: bool = Query(default=False, description="If true, persist the suggested milestones"),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    svc: StudentGoalService = Depends(_svc),
    db: Session = Depends(get_db),
):
    """Generate AI-powered milestone suggestions for a goal using GPT-4o-mini."""
    suggestions = svc.generate_ai_milestones(goal_id, current_user, save=save)

    created_milestones = None
    if save:
        # Reload milestones after saving
        goal = svc.get_goal(goal_id, current_user)
        created_milestones = goal.milestones

    return AIMilestonesResponse(
        suggestions=suggestions,
        created_milestones=created_milestones,
    )
