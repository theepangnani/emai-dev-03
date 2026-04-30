import re
from datetime import datetime
from typing import Literal, Optional, Union
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


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
    monitored_emails: list["MonitoredEmailResponse"] = []

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
    digest_format: Optional[Literal["full", "brief", "actions_only", "sectioned"]] = None
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
# SectionedDigest (#3956 — Phase A of #3905)
# ---------------------------------------------------------------------------

class SectionedDigest(BaseModel):
    """3x3 sectioned digest content produced by generate_sectioned_digest.

    Each section caps at 3 items (enforced by validator). ``overflow`` records
    how many items we would have included if the cap were higher; renderers
    surface this as an "And N more -> View full digest" CTA.

    ``legacy_blob`` is set when the AI JSON parse failed and we fell back to
    the old HTML format — renderers MUST check this first and render the
    legacy HTML instead of the 3x3 layout.
    """
    urgent: list[str] = []
    announcements: list[str] = []
    action_items: list[str] = []
    overflow: dict[str, int] = {}
    legacy_blob: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def fill_missing_fields(cls, data):
        """Fill missing section/overflow keys BEFORE field validators run.

        Pydantic's ``mode="before"`` field validators don't fire when a field
        is absent (the default is used as-is). This ensures the normalize/
        stringify validators always see the caller's intended values — and
        matches the old hand-rolled coercer's ``parsed.get(k, [])`` behavior.
        """
        if not isinstance(data, dict):
            return data
        data = dict(data)  # don't mutate caller's dict
        for key in ("urgent", "announcements", "action_items"):
            data.setdefault(key, [])
        data.setdefault("overflow", {})
        return data

    @field_validator("urgent", "announcements", "action_items", mode="before")
    @classmethod
    def stringify_items(cls, v) -> list[str]:
        if not isinstance(v, list):
            return []
        return [str(x) for x in v if x is not None]

    @field_validator("overflow", mode="before")
    @classmethod
    def normalize_overflow(cls, v) -> dict[str, int]:
        if not isinstance(v, dict):
            return {"urgent": 0, "announcements": 0, "action_items": 0}
        out: dict[str, int] = {}
        for key in ("urgent", "announcements", "action_items"):
            raw = v.get(key, 0)
            try:
                out[key] = max(0, int(raw))
            except (TypeError, ValueError):
                out[key] = 0
        return out

    @field_validator("urgent", "announcements", "action_items")
    @classmethod
    def cap_at_three(cls, v: list[str]) -> list[str]:
        return v[:3]


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
    whatsapp_delivery_status: Optional[str] = None
    email_delivery_status: Optional[str] = None  # #3880

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


# ---------------------------------------------------------------------------
# Monitored Emails (#3178)
# ---------------------------------------------------------------------------

class MonitoredEmailCreate(BaseModel):
    email_address: Optional[str] = None
    sender_name: Optional[str] = None
    label: Optional[str] = None

    @field_validator("email_address")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        v = v.strip().lower()
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", v):
            raise ValueError("Invalid email address")
        return v

    @field_validator("sender_name")
    @classmethod
    def validate_sender_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        return v.strip()

    @model_validator(mode="after")
    def at_least_one(self):
        if not self.email_address and not self.sender_name:
            raise ValueError("Either email_address or sender_name must be provided")
        return self


class MonitoredEmailResponse(BaseModel):
    id: int
    integration_id: int
    email_address: Optional[str] = None
    sender_name: Optional[str] = None
    label: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Unified Digest v2 — parent-level senders + child profiles (#4012, #4014)
# ---------------------------------------------------------------------------


def _normalize_email(v: Optional[str]) -> Optional[str]:
    if v is None or v.strip() == "":
        return None
    v = v.strip().lower()
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", v):
        raise ValueError("Invalid email address")
    return v


class MonitoredSenderCreate(BaseModel):
    email_address: str
    sender_name: Optional[str] = None
    label: Optional[str] = None
    # "all" → applies to every child; list[int] → explicit child profile IDs.
    child_profile_ids: Union[list[int], Literal["all"]]

    @field_validator("email_address")
    @classmethod
    def validate_email(cls, v: str) -> str:
        norm = _normalize_email(v)
        if norm is None:
            raise ValueError("email_address is required")
        return norm

    @field_validator("sender_name")
    @classmethod
    def validate_sender_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        return v.strip()

    @field_validator("label")
    @classmethod
    def validate_label(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        return v.strip()


class MonitoredSenderAssignmentsUpdate(BaseModel):
    child_profile_ids: Union[list[int], Literal["all"]]


class MonitoredSenderAssignmentResponse(BaseModel):
    child_profile_id: int
    first_name: str


class MonitoredSenderResponse(BaseModel):
    id: int
    email_address: Optional[str] = None
    sender_name: Optional[str] = None
    label: Optional[str] = None
    applies_to_all: bool
    child_profile_ids: list[int] = []
    # Paired with child_profile_ids: same assignments with names attached so
    # clients can render per-kid chips without a second lookup (#4082).
    assignments: list[MonitoredSenderAssignmentResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChildSchoolEmailCreate(BaseModel):
    email_address: str

    @field_validator("email_address")
    @classmethod
    def validate_email(cls, v: str) -> str:
        norm = _normalize_email(v)
        if norm is None:
            raise ValueError("email_address is required")
        return norm


class ChildSchoolEmailResponse(BaseModel):
    id: int
    email_address: str
    forwarding_seen_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChildProfileResponse(BaseModel):
    id: int
    first_name: str
    student_id: Optional[int] = None
    school_emails: list[ChildSchoolEmailResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Auto-discovered school addresses (#4329)
# ---------------------------------------------------------------------------


class DiscoveredSchoolEmailResponse(BaseModel):
    id: int
    email_address: str
    sample_sender: Optional[str] = None
    occurrences: int
    first_seen_at: datetime
    last_seen_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiscoveredAssignBody(BaseModel):
    child_profile_id: int


class DiscoveredAssignResponse(BaseModel):
    status: str
    child_profile_id: int


# ---------------------------------------------------------------------------
# Email Digest Dashboard (CB-EDIGEST-002 E1, #4589)
#
# Aggregated read-only view powering the parent dashboard at /email-digest:
# the "what's urgent today, by kid" hero + Mon-Sun week grid + edge states
# (no_kids / paused / first_run / calm / null). Wired to:
#   GET /api/parent/email-digest/dashboard?since=today
# ---------------------------------------------------------------------------


class DashboardUrgentItem(BaseModel):
    """One urgent item rendered on the dashboard.

    `id` is a string so the same shape can later carry non-numeric IDs (e.g.
    if we surface raw email-derived items that pre-date Task creation).
    `source_email_id` mirrors ``Task.source_message_id`` when the item came
    from the digest pipeline.
    """

    id: str
    title: str
    due_date: Optional[datetime] = None
    course_or_context: Optional[str] = None
    source_email_id: Optional[str] = None


class DashboardWeeklyDay(BaseModel):
    """One day of the Mon-Sun week grid for a kid.

    `day` is an ISO date string ("YYYY-MM-DD") — frontend localizes to the
    parent's timezone for rendering.
    """

    day: str
    items: list[DashboardUrgentItem] = []


class DashboardKidView(BaseModel):
    """Per-kid section of the dashboard.

    `id` is the ParentChildProfile.id (NOT the Student.user_id) so the
    frontend keys stably even when the underlying student account is
    detached (CB-PEDI-002 contract).
    """

    id: int
    first_name: str
    urgent_items: list[DashboardUrgentItem] = []
    weekly_deadlines: list[DashboardWeeklyDay] = []
    all_clear: bool


DashboardEmptyState = Literal[
    "calm",
    "no_kids",
    "paused",
    "auth_expired",
    "first_run",
]


class DashboardResponse(BaseModel):
    """Top-level dashboard payload.

    `kids` is ordered by descending count of urgent items (PRD §F6 — kid
    section with the most urgent items appears first). `empty_state` is one
    of the canonical sentinels or null when normal content renders.
    `last_digest_at` reflects the most recent ``DigestDeliveryLog.delivered_at``
    for the parent and is null when no digest has been sent yet.
    """

    kids: list[DashboardKidView] = []
    empty_state: Optional[DashboardEmptyState] = None
    refreshed_at: datetime
    last_digest_at: Optional[datetime] = None
