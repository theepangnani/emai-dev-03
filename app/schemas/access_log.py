from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AccessLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: Optional[int] = None
    user_name: Optional[str] = None
    user_role: Optional[str] = None
    action: str
    timestamp: datetime
    ip_address: Optional[str] = None


class AccessLogResponse(BaseModel):
    content_id: int
    content_title: str
    access_log: list[AccessLogEntry]
    total_views: int
    total_downloads: int
    unique_viewers: int
