from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class OntarioBoardResponse(BaseModel):
    id: int
    code: str
    name: str
    region: Optional[str] = None
    website_url: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CourseCatalogResponse(BaseModel):
    id: int
    board_id: Optional[int] = None
    course_code: str
    course_name: str
    subject_area: str
    grade_level: int
    pathway: str
    credit_value: float
    is_compulsory: bool
    compulsory_category: Optional[str] = None
    prerequisite_codes: Optional[List[str]] = None
    description: Optional[str] = None
    is_ib: bool
    is_ap: bool
    is_shsm: bool
    created_at: datetime

    class Config:
        from_attributes = True


class StudentBoardLink(BaseModel):
    board_id: int
    student_id: Optional[int] = None   # For parents linking a child; omit for students self-linking
    school_name: Optional[str] = Field(default=None, max_length=300)


class StudentBoardResponse(BaseModel):
    id: int
    student_id: int
    board_id: int
    school_name: Optional[str] = None
    linked_at: datetime
    board: OntarioBoardResponse

    class Config:
        from_attributes = True


class CourseCatalogPage(BaseModel):
    items: List[CourseCatalogResponse]
    total: int
    page: int
    page_size: int
    pages: int
