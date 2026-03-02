from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any


# --- Parsed data sub-models ---


class ParsedCourse(BaseModel):
    name: str
    teacher_name: str | None = None
    section: str | None = None


class ParsedAssignment(BaseModel):
    title: str
    description: str | None = None
    due_date: str | None = None  # YYYY-MM-DD
    max_points: float | None = None
    course_name: str | None = None
    status: str | None = None


class ParsedMaterial(BaseModel):
    title: str
    description: str | None = None
    type: str | None = None  # notes, test, lab, assignment, readings, resources
    url: str | None = None


class ParsedAnnouncement(BaseModel):
    title: str | None = None
    body: str
    date: str | None = None  # YYYY-MM-DD
    author: str | None = None


class ParsedGrade(BaseModel):
    assignment_title: str
    score: float | None = None
    max_score: float | None = None
    course_name: str | None = None


class ParsedImportData(BaseModel):
    courses: list[ParsedCourse] = []
    assignments: list[ParsedAssignment] = []
    materials: list[ParsedMaterial] = []
    announcements: list[ParsedAnnouncement] = []
    grades: list[ParsedGrade] = []


# --- Request schemas ---


class CopyPasteImportRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=100000)
    source_hint: str = Field(default="auto", pattern="^(assignment_list|assignment_detail|stream|people|auto)$")
    student_id: int | None = None


class ImportSessionUpdate(BaseModel):
    reviewed_data: dict[str, Any]


# --- Response schemas ---


class ImportSessionResponse(BaseModel):
    id: int
    user_id: int
    student_id: int | None
    source_type: str
    status: str
    parsed_data: dict[str, Any] | None = None
    reviewed_data: dict[str, Any] | None = None
    courses_created: int
    assignments_created: int
    materials_created: int
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ImportSessionListResponse(BaseModel):
    id: int
    source_type: str
    status: str
    courses_created: int
    assignments_created: int
    materials_created: int
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ImportCommitResponse(BaseModel):
    session_id: int
    status: str
    courses_created: int
    assignments_created: int
    materials_created: int


class ImportSessionCreateResponse(BaseModel):
    session_id: int
    status: str
    message: str
