from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

from app.schemas.user import strip_whitespace


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
    role: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1, max_length=1000)
    author: Optional[str] = Field(default=None, max_length=255)

    @field_validator('role', 'text', 'author', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class InspirationMessageUpdate(BaseModel):
    text: Optional[str] = Field(default=None, max_length=1000)
    author: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None

    @field_validator('text', 'author', mode='before')
    @classmethod
    def _strip_whitespace(cls, v: object) -> object:
        return strip_whitespace(v)


class InspirationRandomResponse(BaseModel):
    id: int
    text: str
    author: Optional[str] = None
    role: str
