from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class HolidayDateCreate(BaseModel):
    date: date
    board_name: str = Field(default="YRDSB", max_length=100)
    description: Optional[str] = Field(default=None, max_length=200)


class HolidayDateResponse(BaseModel):
    id: int
    date: date
    board_name: str
    description: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
