"""Report Card API routes (#2018)."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user, require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.student import Student, parent_students
from app.models.user import User, UserRole
from app.schemas.report_card import ReportCardResponse

router = APIRouter(prefix="/report-card", tags=["report-card"])


def _parse_term_dates(term: Optional[str]) -> tuple[Optional[date], Optional[date]]:
    """Parse a term string like 'winter2026' into start/end dates."""
    if not term:
        return None, None

    term_lower = term.lower().strip()

    # Try to extract season and year
    season = None
    year = None
    for s in ("winter", "spring", "summer", "fall"):
        if s in term_lower:
            season = s
            year_str = term_lower.replace(s, "").strip()
            if year_str.isdigit():
                year = int(year_str)
            break

    if not season or not year:
        return None, None

    if season == "fall":
        return date(year, 9, 1), date(year, 12, 31)
    elif season == "winter":
        return date(year, 1, 1), date(year, 4, 30)
    elif season == "spring":
        return date(year, 3, 1), date(year, 6, 30)
    elif season == "summer":
        return date(year, 5, 1), date(year, 8, 31)

    return None, None


@router.get("", response_model=ReportCardResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_report_card(
    request: Request,
    term: Optional[str] = Query(default=None, description="Term like 'winter2026' or 'fall2025'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate report card for the current student."""
    from app.services.report_card_service import ReportCardService

    term_start, term_end = _parse_term_dates(term)
    return ReportCardService.generate(db, current_user.id, term_start, term_end)


@router.get("/children/{student_id}", response_model=ReportCardResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def get_child_report_card(
    request: Request,
    student_id: int,
    term: Optional[str] = Query(default=None, description="Term like 'winter2026' or 'fall2025'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PARENT, UserRole.ADMIN)),
):
    """Parent endpoint: get child's report card."""
    # Verify parent-child relationship (admins bypass)
    if current_user.role != UserRole.ADMIN:
        student = (
            db.query(Student)
            .join(parent_students, parent_students.c.student_id == Student.id)
            .filter(
                parent_students.c.parent_id == current_user.id,
                Student.id == student_id,
            )
            .first()
        )
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not your child or student not found",
            )
        child_user_id = student.user_id
    else:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        child_user_id = student.user_id

    term_start, term_end = _parse_term_dates(term)
    from app.services.report_card_service import ReportCardService

    return ReportCardService.generate(db, child_user_id, term_start, term_end)
