from pydantic import BaseModel
from datetime import datetime


class ResourceLinkBase(BaseModel):
    url: str
    resource_type: str = "external_link"
    title: str | None = None
    topic_heading: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    youtube_video_id: str | None = None
    display_order: int = 0


class ResourceLinkCreate(ResourceLinkBase):
    pass


class ResourceLinkUpdate(BaseModel):
    url: str | None = None
    resource_type: str | None = None
    title: str | None = None
    topic_heading: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    youtube_video_id: str | None = None
    display_order: int | None = None


class ResourceLinkResponse(ResourceLinkBase):
    id: int
    course_content_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ResourceLinkGroupResponse(BaseModel):
    topic_heading: str | None = None
    links: list[ResourceLinkResponse] = []
