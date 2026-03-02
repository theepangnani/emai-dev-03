"""
Admin Events API — inspect the in-memory event log and publish test events.

Endpoints:
  GET  /api/admin/events/recent       — recent events (filterable by type)
  POST /api/admin/events/test-publish — publish a test event for debugging
  GET  /api/admin/events/stats        — event counts by type in the last hour
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.api.deps import require_role
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.events.bus import DomainEvent, get_event_bus
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/events", tags=["admin-events"])


# ── Response schemas ──────────────────────────────────────────────────────────

class EventResponse(BaseModel):
    event_type: str
    occurred_at: datetime
    user_id: int | None
    metadata: dict

    model_config = {"from_attributes": True}


class TestPublishRequest(BaseModel):
    event_type: str = "test.event"
    user_id: int | None = None
    metadata: dict = {}


class TestPublishResponse(BaseModel):
    published: bool
    event_type: str
    occurred_at: datetime


class EventStatsResponse(BaseModel):
    period_hours: int
    counts_by_type: dict[str, int]
    total: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _event_to_response(event: DomainEvent) -> EventResponse:
    return EventResponse(
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        user_id=event.user_id,
        metadata=event.metadata,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/recent", response_model=list[EventResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_recent_events(
    request: Request,
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(50, ge=1, le=500, description="Max events to return"),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> list[EventResponse]:
    """
    Return recent in-memory events, newest first.

    Optionally filter by event_type (e.g. "quiz.attempt_completed").
    Events are kept in a rolling buffer of the last 1 000 events.
    """
    bus = get_event_bus()
    events = bus.get_recent_events(event_type=event_type, limit=limit)
    # Return newest first
    return [_event_to_response(e) for e in reversed(events)]


@router.post("/test-publish", response_model=TestPublishResponse)
@limiter.limit("30/minute", key_func=get_user_id_or_ip)
def test_publish(
    request: Request,
    body: TestPublishRequest,
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> TestPublishResponse:
    """
    Publish a test/synthetic event into the event bus.

    Useful for verifying that handlers are wired up correctly during
    development or staging.
    """
    bus = get_event_bus()
    now = datetime.utcnow()
    event = DomainEvent(
        event_type=body.event_type,
        occurred_at=now,
        user_id=body.user_id,
        metadata=body.metadata,
    )
    bus.publish(event)
    logger.info(
        f"Test event published by admin {_current_user.id}: {body.event_type}"
    )
    return TestPublishResponse(
        published=True,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
    )


@router.get("/stats", response_model=EventStatsResponse)
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
def get_event_stats(
    request: Request,
    period_hours: int = Query(1, ge=1, le=24, description="Look-back window in hours"),
    _current_user: User = Depends(require_role(UserRole.ADMIN)),
) -> EventStatsResponse:
    """
    Return event counts grouped by event_type for the last N hours.

    Only events still in the rolling in-memory log are included.
    """
    bus = get_event_bus()
    cutoff = datetime.utcnow() - timedelta(hours=period_hours)

    # Collect all events in the buffer
    all_events = bus.get_recent_events(limit=1000)
    recent = [e for e in all_events if e.occurred_at >= cutoff]

    counts: dict[str, int] = {}
    for event in recent:
        counts[event.event_type] = counts.get(event.event_type, 0) + 1

    return EventStatsResponse(
        period_hours=period_hours,
        counts_by_type=counts,
        total=sum(counts.values()),
    )
