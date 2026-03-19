from datetime import datetime
from pydantic import BaseModel, Field


class HelpArticleResponse(BaseModel):
    id: int
    slug: str
    title: str
    content: str
    category: str
    role: str | None
    display_order: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=2000)


class HelpChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    page_context: str = Field(default="", max_length=100)
    conversation: list[ConversationMessage] = Field(default_factory=list, max_length=10)


class VideoResponse(BaseModel):
    title: str
    url: str
    provider: str


class SearchResultAction(BaseModel):
    label: str
    route: str


class SearchResultItem(BaseModel):
    entity_type: str
    id: int | None = None
    title: str
    description: str | None = None
    actions: list[SearchResultAction] = []


class HelpChatResponse(BaseModel):
    reply: str
    sources: list[str]
    videos: list[VideoResponse]
    search_results: list[SearchResultItem] = []
    intent: str = "help"  # "help" | "search" | "action"
    suggestion_chips: list[str] = []
