import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.api.deps import get_current_user, require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.db.database import get_db
from app.models.holiday import HolidayDate
from app.models.user import User, UserRole
from app.schemas.holiday_date import (
    HolidayDateCreate,
    HolidayDateUpdate,
    HolidayDateResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/holiday-dates", tags=["Holiday Dates"])


@router.get("", response_model=list[HolidayDateResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def list_holiday_dates(
    request: Request,
    board_code: Optional[str] = Query(None, max_length=20),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List holiday dates, filterable by board_code and date range."""
    query = db.query(HolidayDate)
    if board_code:
        query = query.filter(HolidayDate.board_code == board_code)
    if start_date:
        query = query.filter(HolidayDate.date >= start_date)
    if end_date:
        query = query.filter(HolidayDate.date <= end_date)
    query = query.order_by(HolidayDate.date)
    return query.offset(skip).limit(limit).all()


@router.post("", response_model=HolidayDateResponse, status_code=201)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def create_holiday_date(
    request: Request,
    body: HolidayDateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Create a holiday date (admin only)."""
    holiday = HolidayDate(
        name=body.name,
        date=body.date,
        board_code=body.board_code,
        is_recurring=body.is_recurring,
    )
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.put("/{holiday_id}", response_model=HolidayDateResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def update_holiday_date(
    request: Request,
    holiday_id: int,
    body: HolidayDateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Update a holiday date (admin only)."""
    holiday = db.query(HolidayDate).filter(HolidayDate.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday date not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(holiday, field, value)

    db.commit()
    db.refresh(holiday)
    return holiday


@router.delete("/{holiday_id}", status_code=204)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def delete_holiday_date(
    request: Request,
    holiday_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Delete a holiday date (admin only)."""
    holiday = db.query(HolidayDate).filter(HolidayDate.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday date not found")

    db.delete(holiday)
    db.commit()


def seed_yrdsb_2026_27(db: Session) -> int:
    """Seed YRDSB 2026-27 school year holidays. Returns number of rows inserted."""
    holidays = [
        ("Labour Day", date(2026, 9, 7)),
        ("PA Day (October)", date(2026, 10, 9)),
        ("Thanksgiving", date(2026, 10, 12)),
        ("PA Day (November)", date(2026, 11, 20)),
        ("Winter Break", date(2026, 12, 21)),
        ("Winter Break", date(2026, 12, 22)),
        ("Winter Break", date(2026, 12, 23)),
        ("Winter Break", date(2026, 12, 24)),
        ("Christmas Day", date(2026, 12, 25)),
        ("Boxing Day", date(2026, 12, 26)),
        ("Winter Break", date(2026, 12, 28)),
        ("Winter Break", date(2026, 12, 29)),
        ("Winter Break", date(2026, 12, 30)),
        ("Winter Break", date(2026, 12, 31)),
        ("New Year's Day", date(2027, 1, 1)),
        ("PA Day (January)", date(2027, 1, 29)),
        ("Family Day", date(2027, 2, 15)),
        ("March Break", date(2027, 3, 15)),
        ("March Break", date(2027, 3, 16)),
        ("March Break", date(2027, 3, 17)),
        ("March Break", date(2027, 3, 18)),
        ("March Break", date(2027, 3, 19)),
        ("Good Friday", date(2027, 4, 2)),
        ("Easter Monday", date(2027, 4, 5)),
        ("PA Day (April)", date(2027, 4, 16)),
        ("Victoria Day", date(2027, 5, 24)),
        ("PA Day (June)", date(2027, 6, 25)),
    ]
    inserted = 0
    for name, d in holidays:
        exists = db.query(HolidayDate).filter(
            HolidayDate.date == d,
            HolidayDate.board_code == "YRDSB",
        ).first()
        if not exists:
            db.add(HolidayDate(name=name, date=d, board_code="YRDSB"))
            inserted += 1
    if inserted:
        db.commit()
    return inserted
