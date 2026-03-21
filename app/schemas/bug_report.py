from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class BugReportCreate(BaseModel):
    description: Optional[str] = Field(default=None, max_length=2000)
    page_url: Optional[str] = Field(default=None, max_length=500)
    user_agent: Optional[str] = Field(default=None, max_length=500)


class BugReportResponse(BaseModel):
    id: int
    user_id: int
    description: Optional[str]
    screenshot_url: Optional[str]
    page_url: Optional[str]
    user_agent: Optional[str]
    github_issue_number: Optional[int]
    github_issue_url: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
