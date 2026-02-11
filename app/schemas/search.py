from pydantic import BaseModel
from typing import Optional


class SearchResultItem(BaseModel):
    id: int
    title: str
    subtitle: Optional[str] = None
    entity_type: str  # "course", "study_guide", "task", "course_content"
    url: str  # Frontend route path


class SearchResultGroup(BaseModel):
    entity_type: str
    label: str  # Display label e.g. "Courses", "Study Guides"
    items: list[SearchResultItem]
    total: int


class SearchResponse(BaseModel):
    query: str
    groups: list[SearchResultGroup]
    total: int
