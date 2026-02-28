from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, exists

from app.api.deps import get_db, get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.user import User
from app.models.student import parent_students
from app.models.course import student_courses
from app.models.course_content import CourseContent
from app.models.task import Task

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/progress")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_onboarding_progress(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the onboarding setup checklist progress for the current user."""
    # account_created is always true — they are logged in
    account_created = True

    # email_verified: check the user's email_verified flag
    email_verified = bool(getattr(current_user, "email_verified", True))

    # child_added: parent has at least one linked student
    child_added = db.query(
        exists().where(parent_students.c.parent_id == current_user.id)
    ).scalar()

    # classroom_connected: at least one child has courses enrolled
    classroom_connected = False
    if child_added:
        student_ids = [
            row[0]
            for row in db.execute(
                select(parent_students.c.student_id).where(
                    parent_students.c.parent_id == current_user.id
                )
            ).fetchall()
        ]
        if student_ids:
            classroom_connected = db.query(
                exists().where(student_courses.c.student_id.in_(student_ids))
            ).scalar()

    # material_uploaded: any course content exists for courses the parent's children are in
    material_uploaded = False
    if classroom_connected and student_ids:
        course_ids_subquery = (
            select(student_courses.c.course_id)
            .where(student_courses.c.student_id.in_(student_ids))
        )
        material_uploaded = db.query(
            exists().where(CourseContent.course_id.in_(course_ids_subquery))
        ).scalar()

    # task_created: parent has created at least one task
    task_created = db.query(
        exists().where(Task.created_by_user_id == current_user.id)
    ).scalar()

    # Determine dismissal state — dismissed for 7 days
    dismissed = False
    if current_user.onboarding_dismissed_at:
        elapsed = datetime.now(timezone.utc) - current_user.onboarding_dismissed_at.replace(
            tzinfo=timezone.utc
        )
        dismissed = elapsed < timedelta(days=7)

    return {
        "account_created": account_created,
        "email_verified": email_verified,
        "child_added": child_added,
        "classroom_connected": classroom_connected,
        "material_uploaded": material_uploaded,
        "task_created": task_created,
        "dismissed": dismissed,
    }


@router.post("/dismiss")
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def dismiss_onboarding(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dismiss the onboarding checklist for 7 days."""
    current_user.onboarding_dismissed_at = datetime.now(timezone.utc)
    db.commit()
    return {"success": True}
