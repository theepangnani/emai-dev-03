from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# ParentGmailIntegration
# ---------------------------------------------------------------------------

class ParentGmailIntegrationBase(BaseModel):
    gmail_address: str
    child_school_email: str
    child_first_name: str


class ParentGmailIntegrationCreate(ParentGmailIntegrationBase):
    pass


class ParentGmailIntegrationUpdate(BaseModel):
    gmail_address: Optional[str] = None
    child_school_email: Optional[str] = None
    child_first_name: Optional[str] = None
    is_active: Optional[bool] = None
    paused_until: Optional[datetime] = None


class ParentGmailIntegrationResponse(ParentGmailIntegrationBase):
    id: int
    parent_id: int
    google_id: Optional[str] = None
    connected_at: datetime
    last_synced_at: Optional[datetime] = None
    is_active: bool
    paused_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# ParentDigestSettings
# ---------------------------------------------------------------------------

class ParentDigestSettingsBase(BaseModel):
    digest_enabled: bool = True
    delivery_time: str = "07:00"
    timezone: str = "America/Toronto"
    digest_format: str = "full"
    delivery_channels: str = "in_app,email"
    notify_on_empty: bool = False


class ParentDigestSettingsResponse(ParentDigestSettingsBase):
    id: int
    integration_id: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParentDigestSettingsUpdate(BaseModel):
    digest_enabled: Optional[bool] = None
    delivery_time: Optional[str] = None
    timezone: Optional[str] = None
    digest_format: Optional[str] = None
    delivery_channels: Optional[str] = None
    notify_on_empty: Optional[bool] = None


# ---------------------------------------------------------------------------
# DigestDeliveryLog
# ---------------------------------------------------------------------------

class DigestDeliveryLogResponse(BaseModel):
    id: int
    parent_id: int
    integration_id: int
    email_count: int
    digest_content: Optional[str] = None
    digest_length_chars: Optional[int] = None
    delivered_at: datetime
    channels_used: str
    status: str

    model_config = ConfigDict(from_attributes=True)
