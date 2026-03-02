"""Pydantic schemas for the student portfolio feature."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator

from app.models.portfolio import PortfolioItemType


# ---------------------------------------------------------------------------
# Portfolio Item schemas
# ---------------------------------------------------------------------------

class PortfolioItemCreate(BaseModel):
    item_type: PortfolioItemType
    item_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    display_order: int = 0


class PortfolioItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    display_order: Optional[int] = None


class PortfolioItemResponse(BaseModel):
    id: int
    portfolio_id: int
    item_type: PortfolioItemType
    item_id: Optional[int]
    title: str
    description: Optional[str]
    tags: list[str]
    display_order: int
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, ValueError):
                return []
        return []


# ---------------------------------------------------------------------------
# Portfolio schemas
# ---------------------------------------------------------------------------

class PortfolioCreate(BaseModel):
    title: str = "My Portfolio"
    description: Optional[str] = None
    is_public: bool = False


class PortfolioUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None


class PortfolioResponse(BaseModel):
    id: int
    student_id: int
    title: str
    description: Optional[str]
    is_public: bool
    created_at: datetime
    updated_at: Optional[datetime]
    items: list[PortfolioItemResponse] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Reorder request
# ---------------------------------------------------------------------------

class ReorderRequest(BaseModel):
    item_ids: list[int]
