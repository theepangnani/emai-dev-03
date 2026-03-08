"""Schemas for the Conversation Starters feature."""

from pydantic import BaseModel


class ConversationStarterRequest(BaseModel):
    student_id: int
    course_id: int | None = None


class ConversationStarter(BaseModel):
    prompt: str
    context: str | None = None


class ConversationStartersResponse(BaseModel):
    starters: list[ConversationStarter] = []
    student_name: str
    generated_at: str
