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
