"""FastAPI routes for the Peer Review system.

Endpoints:
  POST   /api/peer-review/assignments               teacher: create
  GET    /api/peer-review/assignments               teacher: list own; student: list all
  GET    /api/peer-review/assignments/{id}          get assignment detail + rubric
  POST   /api/peer-review/assignments/{id}/submit   student: submit work
  POST   /api/peer-review/assignments/{id}/allocate teacher: trigger reviewer allocation
  GET    /api/peer-review/assignments/{id}/my-reviews student: get submissions to review
  POST   /api/peer-review/reviews                   student: submit a peer review
  GET    /api/peer-review/submissions/{id}/reviews  teacher/author: view reviews
  POST   /api/peer-review/assignments/{id}/release  teacher: release reviews to students
  GET    /api/peer-review/assignments/{id}/summary  teacher: all scores summary
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.user import User, UserRole
from app.schemas.peer_review import (
    PeerReviewAssignmentCreate,
    PeerReviewAssignmentResponse,
    PeerReviewCreate,
    PeerReviewResponse,
    PeerReviewSubmissionCreate,
    PeerReviewSubmissionResponse,
    PeerReviewSummary,
)
from app.services.peer_review import PeerReviewService

router = APIRouter(prefix="/peer-review", tags=["peer-review"])


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


@router.post("/assignments", response_model=PeerReviewAssignmentResponse)
def create_assignment(
    data: PeerReviewAssignmentCreate,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Teacher creates a new peer review assignment."""
    return PeerReviewService.create_assignment(current_user.id, data, db)


@router.get("/assignments", response_model=list[PeerReviewAssignmentResponse])
def list_assignments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Teacher sees their own assignments; students see all available ones."""
    if current_user.has_role(UserRole.TEACHER) or current_user.has_role(UserRole.ADMIN):
        return PeerReviewService.list_assignments_for_teacher(current_user.id, db)
    return PeerReviewService.list_assignments_for_student(current_user.id, db)


@router.get("/assignments/{assignment_id}", response_model=PeerReviewAssignmentResponse)
def get_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full assignment details including rubric."""
    return PeerReviewService.get_assignment(assignment_id, db)


# ---------------------------------------------------------------------------
# Student: submit work
# ---------------------------------------------------------------------------


@router.post(
    "/assignments/{assignment_id}/submit",
    response_model=PeerReviewSubmissionResponse,
)
def submit_work(
    assignment_id: int,
    data: PeerReviewSubmissionCreate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Student submits their written work for the peer review assignment."""
    return PeerReviewService.submit_work(assignment_id, current_user.id, data, db)


# ---------------------------------------------------------------------------
# Teacher: allocate reviewers
# ---------------------------------------------------------------------------


@router.post("/assignments/{assignment_id}/allocate")
def allocate_reviewers(
    assignment_id: int,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Teacher triggers round-robin allocation of reviewers to submissions."""
    allocations = PeerReviewService.allocate_reviewers(assignment_id, db)
    return {"allocated": len(allocations), "message": "Reviewers allocated successfully"}


# ---------------------------------------------------------------------------
# Student: get review todo list
# ---------------------------------------------------------------------------


@router.get("/assignments/{assignment_id}/my-reviews")
def get_my_reviews(
    assignment_id: int,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Student retrieves submissions they are assigned to review."""
    return PeerReviewService.get_my_reviews_to_do(current_user.id, assignment_id, db)


# ---------------------------------------------------------------------------
# Student: submit a review
# ---------------------------------------------------------------------------


@router.post("/reviews", response_model=PeerReviewResponse)
def submit_review(
    data: PeerReviewCreate,
    current_user: User = Depends(require_role(UserRole.STUDENT)),
    db: Session = Depends(get_db),
):
    """Student submits rubric scores and written feedback for a peer's work."""
    return PeerReviewService.submit_review(
        allocation_id=data.allocation_id,
        student_id=current_user.id,
        scores=data.scores,
        feedback=data.written_feedback,
        db=db,
    )


# ---------------------------------------------------------------------------
# Teacher / author: view reviews for a submission
# ---------------------------------------------------------------------------


@router.get(
    "/submissions/{submission_id}/reviews",
    response_model=list[PeerReviewResponse],
)
def get_submission_reviews(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Teacher or submission author views the reviews for a submission."""
    return PeerReviewService.get_submission_reviews(submission_id, current_user.id, db)


# ---------------------------------------------------------------------------
# Teacher: release reviews to students
# ---------------------------------------------------------------------------


@router.post(
    "/assignments/{assignment_id}/release",
    response_model=PeerReviewAssignmentResponse,
)
def release_reviews(
    assignment_id: int,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Teacher marks reviews as released so students can see feedback."""
    return PeerReviewService.release_reviews(assignment_id, current_user.id, db)


# ---------------------------------------------------------------------------
# Teacher: summary table
# ---------------------------------------------------------------------------


@router.get(
    "/assignments/{assignment_id}/summary",
    response_model=list[PeerReviewSummary],
)
def get_assignment_summary(
    assignment_id: int,
    current_user: User = Depends(require_role(UserRole.TEACHER, UserRole.ADMIN)),
    db: Session = Depends(get_db),
):
    """Teacher retrieves aggregate scores for all submissions in the assignment."""
    return PeerReviewService.get_assignment_summary(assignment_id, current_user.id, db)
