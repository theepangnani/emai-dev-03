from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models.attendance import AttendanceStatus


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class AttendanceRecordCreate(BaseModel):
    student_id: int
    course_id: int
    date: date
    status: AttendanceStatus
    note: Optional[str] = None


class BulkAttendanceEntry(BaseModel):
    student_id: int
    status: AttendanceStatus
    note: Optional[str] = None


class BulkAttendanceCreate(BaseModel):
    course_id: int
    date: date
    records: list[BulkAttendanceEntry]


class AttendanceRecordUpdate(BaseModel):
    status: Optional[AttendanceStatus] = None
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class AttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    course_id: int
    teacher_id: Optional[int]
    date: date
    status: AttendanceStatus
    note: Optional[str]
    notified_parent: bool
    created_at: datetime
    updated_at: Optional[datetime]

    # Denormalized for convenience
    student_name: Optional[str] = None
    course_name: Optional[str] = None


class AttendanceSummary(BaseModel):
    student_id: int
    student_name: str
    course_id: Optional[int] = None
    course_name: Optional[str] = None
    present_count: int
    absent_count: int
    late_count: int
    excused_count: int
    total_days: int
    attendance_pct: float  # 0-100


class CourseAttendanceReport(BaseModel):
    course_id: int
    course_name: str
    start_date: date
    end_date: date
    student_summaries: list[AttendanceSummary]


class BulkAttendanceResponse(BaseModel):
    created: int
    updated: int
    records: list[AttendanceResponse]
