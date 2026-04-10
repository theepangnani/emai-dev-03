import re
from datetime import datetime
from typing import Literal, Optional
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# ParentGmailIntegration
# ---------------------------------------------------------------------------

class ParentGmailIntegrationBase(BaseModel):
    gmail_address: str
    child_school_email: Optional[str] = None
    child_first_name: Optional[str] = None


class ParentGmailIntegrationCreate(ParentGmailIntegrationBase):
    pass


class ParentGmailIntegrationUpdate(BaseModel):
    gmail_address: Optional[str] = None
    child_school_email: Optional[str] = None
    child_first_name: Optional[str] = None
    is_active: Optional[bool] = None
    paused_until: Optional[datetime] = None
    whatsapp_phone: Optional[str] = None


class ParentGmailIntegrationResponse(ParentGmailIntegrationBase):
    id: int
    parent_id: int
    google_id: Optional[str] = None
    connected_at: datetime
    last_synced_at: Optional[datetime] = None
    is_active: bool
    paused_until: Optional[datetime] = None
    whatsapp_phone: Optional[str] = None
    whatsapp_verified: bool = False
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
    digest_format: Optional[Literal["full", "brief", "actions_only"]] = None
    delivery_channels: Optional[str] = None
    notify_on_empty: Optional[bool] = None

    @field_validator("delivery_time")
    @classmethod
    def validate_delivery_time(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r"^\d{2}:\d{2}$", v):
            raise ValueError("delivery_time must be in HH:MM format")
        hours, minutes = v.split(":")
        if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
            raise ValueError("delivery_time must be a valid time (00:00–23:59)")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in available_timezones():
            raise ValueError(f"Invalid timezone: {v}")
        return v


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
    channels_used: Optional[str] = None
    status: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# WhatsApp verification
# ---------------------------------------------------------------------------

class WhatsAppVerifyRequest(BaseModel):
    phone: str  # E.164 format e.g. +14165551234

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^\+[1-9]\d{6,14}$", v):
            raise ValueError("Phone must be in E.164 format (e.g. +14165551234)")
        return v


class WhatsAppOTPRequest(BaseModel):
    otp_code: str

    @field_validator("otp_code")
    @classmethod
    def validate_otp(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 6:
            raise ValueError("OTP must be a 6-digit code")
        return v
