from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel

from app.models.newsletter import NewsletterStatus, NewsletterAudience


class NewsletterCreate(BaseModel):
    title: str
    subject: str
    content: str
    html_content: Optional[str] = None
    audience: NewsletterAudience = NewsletterAudience.ALL


class NewsletterUpdate(BaseModel):
    title: Optional[str] = None
    subject: Optional[str] = None
    content: Optional[str] = None
    html_content: Optional[str] = None
    audience: Optional[NewsletterAudience] = None


class NewsletterResponse(BaseModel):
    id: int
    created_by: int
    title: str
    subject: str
    content: str
    html_content: Optional[str] = None
    audience: NewsletterAudience
    status: NewsletterStatus
    scheduled_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    recipient_count: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class NewsletterGenerateRequest(BaseModel):
    topic: str
    key_points: list[str]
    audience: NewsletterAudience = NewsletterAudience.ALL
    tone: Literal["formal", "friendly", "informative"] = "friendly"


class NewsletterScheduleRequest(BaseModel):
    scheduled_at: datetime


class NewsletterSendResponse(BaseModel):
    sent_count: int
    failed_count: int
    newsletter_id: int


class NewsletterTemplateResponse(BaseModel):
    id: int
    name: str
    description: str
    content_template: str
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
