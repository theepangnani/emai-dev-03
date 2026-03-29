from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.models.user import User
from app.schemas.journey_hint import JourneyHintAction, JourneyHintResponse, JourneyHintResult
from app.services import journey_hint_service

router = APIRouter(prefix="/journey", tags=["journey"])


@router.get("/hints", response_model=JourneyHintResult)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_journey_hint(
    request: Request,
    page: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return at most one applicable journey hint for the current page."""
    result = journey_hint_service.get_applicable_hint(db, current_user, page=page)
    if result:
        journey_hint_service.record_shown(db, current_user.id, result["hint_key"])
        return JourneyHintResult(hint=JourneyHintResponse(**result))
    return JourneyHintResult(hint=None)


# suppress-all MUST be before {hint_key} routes to avoid path parameter matching
@router.post("/hints/suppress-all", response_model=JourneyHintAction)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
def suppress_all_hints(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suppress ALL journey hints (nuclear option)."""
    journey_hint_service.suppress_all_hints(db, current_user.id)
    return JourneyHintAction(success=True, message="All hints suppressed")


@router.post("/hints/{hint_key}/dismiss", response_model=JourneyHintAction)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def dismiss_hint(
    request: Request,
    hint_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently dismiss a journey hint."""
    journey_hint_service.dismiss_hint(db, current_user.id, hint_key)
    return JourneyHintAction(success=True, message="Hint dismissed")


@router.post("/hints/{hint_key}/snooze", response_model=JourneyHintAction)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def snooze_hint(
    request: Request,
    hint_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Snooze a journey hint for 7 days."""
    journey_hint_service.snooze_hint(db, current_user.id, hint_key)
    return JourneyHintAction(success=True, message="Hint snoozed for 7 days")
