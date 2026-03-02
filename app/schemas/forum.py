from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ForumCategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    board_id: Optional[int] = None
    display_order: int
    is_active: bool
    thread_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class ForumThreadCreate(BaseModel):
    category_id: int
    title: str = Field(..., max_length=200)
    body: str


class ForumThreadResponse(BaseModel):
    id: int
    category_id: int
    author_id: int
    author_name: str
    title: str
    body: str
    is_pinned: bool
    is_locked: bool
    view_count: int
    reply_count: int
    is_moderated: bool
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ForumPostCreate(BaseModel):
    body: str
    parent_post_id: Optional[int] = None


class ForumPostResponse(BaseModel):
    id: int
    thread_id: int
    author_id: int
    author_name: str
    body: str
    like_count: int
    is_moderated: bool
    approved_at: Optional[datetime] = None
    parent_post_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    replies: list["ForumPostResponse"] = []

    model_config = {"from_attributes": True}


# Resolve forward reference
ForumPostResponse.model_rebuild()


class ForumListResponse(BaseModel):
    items: list[ForumThreadResponse]
    total: int
    page: int
    limit: int
    pages: int
