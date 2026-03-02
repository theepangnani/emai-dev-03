from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role, get_db
from app.models.user import User, UserRole
from app.schemas.wellness import (
    WellnessCheckInCreate,
    WellnessCheckInResponse,
    WellnessTrendResponse,
    WellnessSummary,
)
from app.services.wellness import WellnessService

router = APIRouter(tags=["wellness"])


def _get_service(db: Session = Depends(get_db)) -> WellnessService:
    return WellnessService(db)


# ---------------------------------------------------------------------------
# Student endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/wellness/check-in",
    response_model=WellnessCheckInResponse,
    status_code=status.HTTP_200_OK,
    summary="Create or update today's wellness check-in",
)
def submit_check_in(
    data: WellnessCheckInCreate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    service: WellnessService = Depends(_get_service),
):
    """Students submit (or update) their daily mood/energy/stress check-in."""
    return service.create_check_in(student_id=current_user.id, data=data)


@router.get(
    "/wellness/today",
    response_model=WellnessCheckInResponse | None,
    summary="Get today's wellness check-in for the current student",
)
def get_today(
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    service: WellnessService = Depends(_get_service),
):
    """Return today's check-in for the authenticated student, or null if not yet submitted."""
    return service.get_today(student_id=current_user.id)


@router.get(
    "/wellness/trend",
    response_model=WellnessTrendResponse,
    summary="Get 7-day wellness trend for the current student",
)
def get_self_trend(
    days: int = Query(default=7, ge=1, le=30, description="Number of days to look back"),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    service: WellnessService = Depends(_get_service),
):
    """Return mood/energy/stress trend for the authenticated student."""
    return service.get_trend(student_id=current_user.id, days=days)


# ---------------------------------------------------------------------------
# Teacher / Admin: view non-private summary for a student
# ---------------------------------------------------------------------------


@router.get(
    "/wellness/student/{student_id}/summary",
    response_model=WellnessSummary,
    summary="Get wellness summary for a student (teacher/admin/parent view)",
)
def get_student_summary(
    student_id: int,
    current_user: User = Depends(
        require_role(UserRole.TEACHER, UserRole.ADMIN, UserRole.PARENT)
    ),
    service: WellnessService = Depends(_get_service),
    db: Session = Depends(get_db),
):
    """
    Teachers and admins can view the non-private wellness summary for any student.
    Parents can view their linked child's summary (private entries excluded).
    """
    if current_user.has_role(UserRole.PARENT):
        # Verify the parent-child link first
        service.get_parent_child_wellness(
            parent_id=current_user.id, student_id=student_id
        )

    return service.get_student_summary(student_id=student_id, exclude_private=True)


# ---------------------------------------------------------------------------
# Parent: full trend for their child (non-private only)
# ---------------------------------------------------------------------------


@router.get(
    "/wellness/student/{student_id}/trend",
    response_model=WellnessTrendResponse,
    summary="Get wellness trend for a linked child (parent view)",
)
def get_child_trend(
    student_id: int,
    days: int = Query(default=7, ge=1, le=30),
    current_user: User = Depends(require_role(UserRole.PARENT)),
    service: WellnessService = Depends(_get_service),
):
    """
    Parents can view the 7-day trend for their linked child.
    Private check-ins are excluded.
    """
    return service.get_parent_child_wellness(
        parent_id=current_user.id, student_id=student_id
    )
