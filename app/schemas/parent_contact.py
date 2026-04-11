import re
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ── Parent Contact ──────────────────────────────────────────────────────
class ParentContactCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    school_name: Optional[str] = Field(None, max_length=255)
    child_name: Optional[str] = Field(None, max_length=255)
    child_grade: Optional[str] = Field(None, max_length=20)
    status: str = "lead"
    source: str = "manual"
    tags: list[str] = Field(default_factory=list)
    consent_given: bool = False

    @field_validator("full_name", "school_name", "child_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v if v else None
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, v):
        if not v:
            return v
        v = re.sub(r"[\s\-\(\)\.]+", "", str(v))
        if v.startswith("1") and len(v) == 11:
            v = "+" + v
        elif not v.startswith("+"):
            v = "+1" + v
        if not re.match(r"^\+[1-9]\d{9,14}$", v):
            raise ValueError("Phone must be E.164 format (e.g., +14165551234)")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid = {"lead", "contacted", "interested", "converted", "archived", "unresponsive"}
        if v not in valid:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("source")
    @classmethod
    def validate_source(cls, v):
        valid = {"manual", "csv_import", "waitlist", "referral"}
        if v not in valid:
            raise ValueError(f"Invalid source. Must be one of: {', '.join(sorted(valid))}")
        return v


class ParentContactUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    school_name: Optional[str] = Field(None, max_length=255)
    child_name: Optional[str] = Field(None, max_length=255)
    child_grade: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[list[str]] = None
    linked_user_id: Optional[int] = None
    consent_given: Optional[bool] = None

    @field_validator("full_name", "school_name", "child_name", mode="before")
    @classmethod
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, v):
        if not v:
            return v
        v = re.sub(r"[\s\-\(\)\.]+", "", str(v))
        if v.startswith("1") and len(v) == 11:
            v = "+" + v
        elif not v.startswith("+"):
            v = "+1" + v
        if not re.match(r"^\+[1-9]\d{9,14}$", v):
            raise ValueError("Phone must be E.164 format (e.g., +14165551234)")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is None:
            return v
        valid = {"lead", "contacted", "interested", "converted", "archived", "unresponsive"}
        if v not in valid:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(sorted(valid))}")
        return v

    @field_validator("source")
    @classmethod
    def validate_source(cls, v):
        if v is None:
            return v
        valid = {"manual", "csv_import", "waitlist", "referral"}
        if v not in valid:
            raise ValueError(f"Invalid source. Must be one of: {', '.join(sorted(valid))}")
        return v


class ParentContactResponse(BaseModel):
    id: int
    full_name: str
    email: str | None = None
    phone: str | None = None
    school_name: str | None = None
    child_name: str | None = None
    child_grade: str | None = None
    status: str
    source: str
    tags: list[str] = []
    linked_user_id: int | None = None
    consent_given: bool
    consent_date: datetime | None = None
    created_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("tags", mode="before")
    @classmethod
    def tags_or_empty(cls, v):
        if v is None:
            return []
        return list(v)


class ParentContactListResponse(BaseModel):
    items: list[ParentContactResponse]
    total: int


class ParentContactStats(BaseModel):
    total: int
    by_status: dict[str, int]
    recent_outreach_count: int
    contacts_without_consent: int


# ── Contact Notes ───────────────────────────────────────────────────────
# ── Bulk Operations ────────────────────────────────────────────────────
class BulkDeleteRequest(BaseModel):
    ids: list[int] = Field(min_length=1)


class BulkStatusRequest(BaseModel):
    ids: list[int] = Field(min_length=1)
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid = {"lead", "contacted", "interested", "converted", "archived", "unresponsive"}
        if v not in valid:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(sorted(valid))}")
        return v


class BulkTagRequest(BaseModel):
    ids: list[int] = Field(min_length=1)
    tag: str = Field(min_length=1, max_length=50)
    action: Literal["add", "remove"]


# ── Contact Notes ───────────────────────────────────────────────────────
class ContactNoteCreate(BaseModel):
    note_text: str = Field(min_length=1)


class ContactNoteResponse(BaseModel):
    id: int
    parent_contact_id: int
    note_text: str
    created_by_user_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
