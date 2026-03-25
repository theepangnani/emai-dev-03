from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CalendarFeedCreate(BaseModel):
    url: str


class CalendarFeedResponse(BaseModel):
    id: int
    url: str
    name: Optional[str] = None
    last_synced: Optional[datetime] = None
    event_count: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CalendarEventResponse(BaseModel):
    id: int
    feed_id: int
    uid: str
    title: str
    description: Optional[str] = None
    start_date: datetime
    end_date: Optional[datetime] = None
    all_day: bool
    location: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── ICS File Upload schemas ──────────────────────────────────


class ICSEventPreview(BaseModel):
    """A single parsed event from an uploaded .ics file."""
    index: int
    summary: str
    dtstart: datetime
    dtend: Optional[datetime] = None
    description: Optional[str] = None
    location: Optional[str] = None


class ICSParseResponse(BaseModel):
    """Response from parsing an uploaded .ics file (preview before import)."""
    events: list[ICSEventPreview]
    total: int


class ICSImportRequest(BaseModel):
    """Request to import selected events from a previously parsed .ics file."""
    selected_indices: Optional[list[int]] = None


class ICSImportResponse(BaseModel):
    """Result of importing ICS events as tasks."""
    created_count: int
    skipped_count: int
    errors: list[str]
