from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class InspirationMessageResponse(BaseModel):
    id: int
    role: str
    text: str
    author: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InspirationMessageCreate(BaseModel):
    role: str
    text: str
    author: Optional[str] = None


class InspirationMessageUpdate(BaseModel):
    text: Optional[str] = None
    author: Optional[str] = None
    is_active: Optional[bool] = None


class InspirationRandomResponse(BaseModel):
    id: int
    text: str
    author: Optional[str] = None
    role: str
