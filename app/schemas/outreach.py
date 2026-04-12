from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Outreach Templates ──────────────────────────────────────────────────
class OutreachTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    subject: Optional[str] = Field(None, max_length=500)
    body_html: Optional[str] = None
    body_text: str = Field(min_length=1)
    template_type: str = "email"  # email/whatsapp/sms
    variables: list[str] = Field(default_factory=list)


class OutreachTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    subject: Optional[str] = Field(None, max_length=500)
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    template_type: Optional[str] = None
    variables: Optional[list[str]] = None
    is_active: Optional[bool] = None


class OutreachTemplateResponse(BaseModel):
    id: int
    name: str
    subject: str | None = None
    body_html: str | None = None
    body_text: str
    template_type: str
    variables: list[str] = []
    is_active: bool
    created_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("variables", mode="before")
    @classmethod
    def variables_or_empty(cls, v):
        if v is None:
            return []
        return list(v)


class OutreachTemplateListResponse(BaseModel):
    items: list[OutreachTemplateResponse]
    total: int


class OutreachTemplatePreviewRequest(BaseModel):
    variable_values: dict[str, str] = Field(default_factory=dict)


class OutreachTemplatePreviewResponse(BaseModel):
    rendered_subject: str | None = None
    rendered_html: str | None = None
    rendered_text: str


# ── Outreach Send ───────────────────────────────────────────────────────
class SendOutreachRequest(BaseModel):
    parent_contact_ids: list[int] = Field(min_length=1)
    template_id: Optional[int] = None
    channel: Literal["email", "whatsapp", "sms"]
    custom_subject: Optional[str] = None
    custom_body: Optional[str] = None


class SendOutreachErrorDetail(BaseModel):
    contact_id: int
    contact_name: str
    error: str


class SendOutreachResponse(BaseModel):
    sent_count: int
    failed_count: int
    errors: list[SendOutreachErrorDetail] = []


class OutreachLogResponse(BaseModel):
    id: int
    parent_contact_id: int | None = None
    contact_name: str | None = None
    template_id: int | None = None
    template_name: str | None = None
    channel: str
    status: str
    recipient_detail: str | None = None
    body_snapshot: str | None = None
    sent_by_user_id: int | None = None
    error_message: str | None = None
    created_at: datetime


class OutreachLogListResponse(BaseModel):
    items: list[OutreachLogResponse]
    total: int


class OutreachStatsResponse(BaseModel):
    total_sent: int
    sent_today: int
    sent_this_week: int
    by_channel: dict[str, int]
    by_status: dict[str, int]


# ── Duplicate Detection ─────────────────────────────────────────────────
class DuplicateGroupResponse(BaseModel):
    email: str
    contacts: list  # list of ParentContactResponse — avoid circular import
