from pydantic import BaseModel, Field


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


class HelpChatResponse(BaseModel):
    reply: str
    sources: list[str]
    videos: list[VideoResponse]
