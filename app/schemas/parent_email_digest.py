"""Pydantic schemas for Parent Email Digest feature.

Stub file — will be replaced with full implementation when the schemas branch is merged.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class IntegrationResponse(BaseModel):
    id: int
    parent_user_id: int
    gmail_address: str
    status: str
    paused_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DigestSettingsResponse(BaseModel):
    id: int
    integration_id: int
    delivery_time: str
    timezone: str
    include_ai_summary: bool
    include_action_items: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DigestSettingsUpdate(BaseModel):
    delivery_time: Optional[str] = None
    timezone: Optional[str] = None
    include_ai_summary: Optional[bool] = None
    include_action_items: Optional[bool] = None


class DeliveryLogResponse(BaseModel):
    id: int
    integration_id: int
    status: str
    email_count: int
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeliveryLogDetailResponse(DeliveryLogResponse):
    digest_content: Optional[str] = None
