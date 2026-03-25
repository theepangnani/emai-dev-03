from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.models.calendar_feed import CalendarFeed
from app.models.calendar_event import CalendarEvent
from app.api.deps import get_current_user
from app.core.rate_limit import limiter, get_user_id_or_ip
from app.schemas.calendar_import import (
    CalendarFeedCreate, CalendarFeedResponse, CalendarEventResponse,
    ICSParseResponse, ICSEventPreview, ICSImportResponse,
)
from app.services.calendar_import_service import sync_calendar_feed, fetch_and_parse_ics
from app.services.ics_import_service import parse_ics_file, import_events_as_tasks

router = APIRouter(tags=["Calendar Import"])


@router.post("/import/calendar", response_model=CalendarFeedResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def add_calendar_feed(
    request: Request,
    body: CalendarFeedCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new ICS calendar feed and perform initial sync."""
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Validate URL by fetching
    try:
        cal_name, events = await fetch_and_parse_ics(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    feed = CalendarFeed(
        user_id=current_user.id,
        url=url,
        name=cal_name,
        last_synced=datetime.now(timezone.utc),
        event_count=len(events),
    )
    db.add(feed)
    db.flush()

    # Insert events
    for evt_data in events:
        db.add(CalendarEvent(
            feed_id=feed.id,
            user_id=current_user.id,
            **evt_data,
        ))

    db.commit()
    db.refresh(feed)
    return feed


@router.get("/import/calendar", response_model=list[CalendarFeedResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
async def list_calendar_feeds(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the current user's calendar feeds."""
    feeds = (
        db.query(CalendarFeed)
        .filter(CalendarFeed.user_id == current_user.id)
        .order_by(CalendarFeed.created_at.desc())
        .all()
    )
    return feeds


@router.post("/import/calendar/{feed_id}/sync", response_model=CalendarFeedResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def sync_feed(
    request: Request,
    feed_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually re-sync a calendar feed."""
    feed = (
        db.query(CalendarFeed)
        .filter(CalendarFeed.id == feed_id, CalendarFeed.user_id == current_user.id)
        .first()
    )
    if not feed:
        raise HTTPException(status_code=404, detail="Calendar feed not found")

    try:
        await sync_calendar_feed(db, feed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    db.refresh(feed)
    return feed


@router.delete("/import/calendar/{feed_id}")
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def delete_calendar_feed(
    request: Request,
    feed_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a calendar feed and all its events."""
    feed = (
        db.query(CalendarFeed)
        .filter(CalendarFeed.id == feed_id, CalendarFeed.user_id == current_user.id)
        .first()
    )
    if not feed:
        raise HTTPException(status_code=404, detail="Calendar feed not found")

    db.delete(feed)
    db.commit()
    return {"detail": "Calendar feed deleted"}


@router.get("/calendar-events", response_model=list[CalendarEventResponse])
@limiter.limit("60/minute", key_func=get_user_id_or_ip)
async def list_calendar_events(
    request: Request,
    start: Optional[str] = Query(None, description="ISO date filter start"),
    end: Optional[str] = Query(None, description="ISO date filter end"),
    feed_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List calendar events for the current user with optional date range filter."""
    query = db.query(CalendarEvent).filter(CalendarEvent.user_id == current_user.id)

    if feed_id:
        query = query.filter(CalendarEvent.feed_id == feed_id)

    if start:
        try:
            start_dt = datetime.fromisoformat(start)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start date format")
        query = query.filter(CalendarEvent.start_date >= start_dt)

    if end:
        try:
            end_dt = datetime.fromisoformat(end)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end date format")
        query = query.filter(CalendarEvent.start_date <= end_dt)

    events = query.order_by(CalendarEvent.start_date.asc()).all()
    return events


# ── ICS File Upload endpoints ────────────────────────────────


@router.post("/import/ics/parse", response_model=ICSParseResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def parse_ics_upload(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload an .ics file and return parsed events for preview."""
    if not file.filename or not file.filename.lower().endswith(".ics"):
        raise HTTPException(status_code=400, detail="Only .ics files are accepted")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5 MB limit
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    try:
        events = parse_ics_file(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    previews = [
        ICSEventPreview(
            index=i,
            summary=e["summary"],
            dtstart=e["dtstart"],
            dtend=e.get("dtend"),
            description=e.get("description"),
            location=e.get("location"),
        )
        for i, e in enumerate(events)
    ]
    return ICSParseResponse(events=previews, total=len(previews))


@router.post("/import/ics", response_model=ICSImportResponse)
@limiter.limit("10/minute", key_func=get_user_id_or_ip)
async def import_ics_upload(
    request: Request,
    file: UploadFile = File(...),
    selected_indices: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload an .ics file and import events as tasks.

    Optionally pass selected_indices as a comma-separated string of
    event indices to import (e.g. "0,2,5"). If omitted, all events
    are imported.
    """
    if not file.filename or not file.filename.lower().endswith(".ics"):
        raise HTTPException(status_code=400, detail="Only .ics files are accepted")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    try:
        events = parse_ics_file(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    indices = None
    if selected_indices:
        try:
            indices = [int(x.strip()) for x in selected_indices.split(",")]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid selected_indices format")

    result = import_events_as_tasks(db, current_user, events, indices)
    return ICSImportResponse(**result)
