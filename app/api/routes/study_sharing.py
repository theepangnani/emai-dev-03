"""Parent-Child Study Link: share study guides with children and track viewing."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.logging_config import get_logger
from app.db.database import get_db
from app.models.notification import Notification, NotificationType
from app.models.student import Student, parent_students
from app.models.study_guide import StudyGuide
from app.models.user import User, UserRole

logger = get_logger(__name__)

router = APIRouter(prefix="/study-guides", tags=["study-sharing"])


# ── Schemas ──────────────────────────────────────────────────────────

class ShareRequest(BaseModel):
    student_id: int  # Student table ID (not user_id)


class ShareResponse(BaseModel):
    id: int
    title: str
    shared_with_user_id: int
    shared_with_name: str
    shared_at: datetime

    class Config:
        from_attributes = True


class SharedGuideStatus(BaseModel):
    id: int
    title: str
    guide_type: str
    shared_with_user_id: int | None
    shared_with_name: str | None
    shared_at: datetime | None
    viewed_at: datetime | None
    viewed_count: int
    status: str  # "not_shared", "shared", "viewed"
    created_at: datetime

    class Config:
        from_attributes = True


class SharedWithMeGuide(BaseModel):
    id: int
    title: str
    content: str
    guide_type: str
    shared_by_name: str
    shared_at: datetime
    viewed_at: datetime | None
    viewed_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Helpers ──────────────────────────────────────────────────────────

def _get_child_user_ids(db: Session, parent_user_id: int) -> dict[int, tuple[int, str]]:
    """Return {student.id: (user.id, user.full_name)} for parent's linked children."""
    rows = (
        db.query(Student, User)
        .join(parent_students, parent_students.c.student_id == Student.id)
        .join(User, User.id == Student.user_id)
        .filter(parent_students.c.parent_id == parent_user_id)
        .all()
    )
    return {s.id: (u.id, u.full_name) for s, u in rows}


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/{guide_id}/share", response_model=ShareResponse)
def share_guide_with_child(
    guide_id: int,
    body: ShareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Parent shares one of their study guides with a linked child."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == guide_id,
        StudyGuide.user_id == current_user.id,
        StudyGuide.archived_at.is_(None),
    ).first()
    if not guide:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Study guide not found")

    children = _get_child_user_ids(db, current_user.id)
    if body.student_id not in children:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your linked child")

    child_user_id, child_name = children[body.student_id]

    guide.shared_with_user_id = child_user_id
    guide.shared_at = datetime.now(timezone.utc)
    guide.viewed_at = None
    guide.viewed_count = 0

    # Create notification for the child
    notif = Notification(
        user_id=child_user_id,
        type=NotificationType.STUDY_GUIDE_SHARED,
        title=f"{current_user.full_name} shared a study guide with you",
        content=f'"{guide.title}" — open it to start studying!',
        link=f"/study/guide/{guide.id}",
    )
    db.add(notif)
    db.commit()
    db.refresh(guide)

    logger.info("Parent %s shared guide %s with child %s", current_user.id, guide_id, child_user_id)
    return ShareResponse(
        id=guide.id,
        title=guide.title,
        shared_with_user_id=child_user_id,
        shared_with_name=child_name,
        shared_at=guide.shared_at,
    )


@router.get("/shared-with-me", response_model=list[SharedWithMeGuide])
def get_shared_with_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.STUDENT)),
):
    """Student sees study guides shared by their parent."""
    guides = (
        db.query(StudyGuide, User)
        .join(User, User.id == StudyGuide.user_id)
        .filter(
            StudyGuide.shared_with_user_id == current_user.id,
            StudyGuide.archived_at.is_(None),
        )
        .order_by(StudyGuide.shared_at.desc())
        .all()
    )
    return [
        SharedWithMeGuide(
            id=g.id,
            title=g.title,
            content=g.content,
            guide_type=g.guide_type,
            shared_by_name=u.full_name,
            shared_at=g.shared_at,
            viewed_at=g.viewed_at,
            viewed_count=g.viewed_count,
            created_at=g.created_at,
        )
        for g, u in guides
    ]


@router.post("/{guide_id}/mark-viewed")
def mark_guide_viewed(
    guide_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a shared study guide as viewed (auto-called when student opens it)."""
    guide = db.query(StudyGuide).filter(
        StudyGuide.id == guide_id,
        StudyGuide.shared_with_user_id == current_user.id,
    ).first()
    if not guide:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shared guide not found")

    now = datetime.now(timezone.utc)
    if guide.viewed_at is None:
        guide.viewed_at = now
    guide.viewed_count = (guide.viewed_count or 0) + 1
    db.commit()
    return {"status": "ok", "viewed_at": guide.viewed_at.isoformat(), "viewed_count": guide.viewed_count}


@router.get("/shared-status", response_model=list[SharedGuideStatus])
def get_shared_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT)),
):
    """Parent sees sharing status of all their study guides."""
    guides = (
        db.query(StudyGuide)
        .filter(
            StudyGuide.user_id == current_user.id,
            StudyGuide.archived_at.is_(None),
        )
        .order_by(StudyGuide.created_at.desc())
        .all()
    )

    # Bulk-load child names
    child_user_ids = {g.shared_with_user_id for g in guides if g.shared_with_user_id}
    name_map: dict[int, str] = {}
    if child_user_ids:
        users = db.query(User).filter(User.id.in_(child_user_ids)).all()
        name_map = {u.id: u.full_name for u in users}

    results = []
    for g in guides:
        if g.shared_with_user_id and g.viewed_at:
            st = "viewed"
        elif g.shared_with_user_id:
            st = "shared"
        else:
            st = "not_shared"

        results.append(SharedGuideStatus(
            id=g.id,
            title=g.title,
            guide_type=g.guide_type,
            shared_with_user_id=g.shared_with_user_id,
            shared_with_name=name_map.get(g.shared_with_user_id) if g.shared_with_user_id else None,
            shared_at=g.shared_at,
            viewed_at=g.viewed_at,
            viewed_count=g.viewed_count or 0,
            status=st,
            created_at=g.created_at,
        ))
    return results
