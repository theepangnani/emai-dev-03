from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class HolidayDateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    date: date
    board_code: Optional[str] = Field(default=None, max_length=20)
    is_recurring: bool = False


class HolidayDateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    date: Optional[date] = None
    board_code: Optional[str] = Field(default=None, max_length=20)
    is_recurring: Optional[bool] = None


class HolidayDateResponse(BaseModel):
    id: int
    name: str
    date: date
    board_code: Optional[str]
    is_recurring: bool
    created_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
