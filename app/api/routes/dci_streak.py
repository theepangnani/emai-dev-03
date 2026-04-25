"""DCI Check-in Streak API (CB-DCI-001 M0-8, #4145).

Exposes the kid-facing streak read endpoint. The full ``/api/dci/*`` router
surface is owned by other M0 stripes (M0-3 / M0-4) — this file is intentionally
narrow and only ships the GET endpoint required by M0-8.

Auth model:
- A kid (STUDENT user) can read their own streak.
- A linked PARENT can read any of their children's streaks.
- Anyone else → 403.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.rate_limit import get_user_id_or_ip, limiter
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.services.dci_streak_service import get_streak

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dci", tags=["dci"])


def _kid_visible_to(db: Session, user: User, kid_id: int) -> bool:
    """Return True if ``user`` may read the streak for ``kid_id``
    (= ``students.id``)."""
    student = db.query(Student).filter(Student.id == kid_id).first()
    if student is None:
        return False

    # Kid reading own streak
    if user.has_role(UserRole.STUDENT) and student.user_id == user.id:
        return True

    # Linked parent
    if user.has_role(UserRole.PARENT):
        link = (
            db.query(parent_students.c.student_id)
            .filter(
                parent_students.c.parent_id == user.id,
                parent_students.c.student_id == kid_id,
            )
            .first()
        )
        if link is not None:
            return True

    return False


@router.get("/streak/{kid_id}")
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_checkin_streak(
    request: Request,
    kid_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return ``{current, longest, last_checkin_date, days_until_next_milestone}``
    for the given kid.

    Never-guilt: payload deliberately omits break events and missed-day counts.
    """
    if not _kid_visible_to(db, current_user, kid_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not allowed to read this kid's streak",
        )
    return get_streak(db, kid_id)
