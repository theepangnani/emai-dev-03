from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class HolidayDateCreate(BaseModel):
    date: date
    name: str = Field(min_length=1, max_length=100)
    board: str = Field(default="YRDSB", max_length=50)


class HolidayDateResponse(BaseModel):
    id: int
    date: date
    name: str
    board: str | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
