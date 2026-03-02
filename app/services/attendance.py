"""Attendance service — business logic for recording and reporting attendance."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceRecord, AttendanceAlert, AttendanceStatus
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.models.course import Course
from app.models.student import Student, parent_students
from app.schemas.attendance import (
    AttendanceSummary,
    CourseAttendanceReport,
    AttendanceResponse,
    BulkAttendanceEntry,
)


def _to_response(record: AttendanceRecord) -> AttendanceResponse:
    """Convert an ORM AttendanceRecord to an AttendanceResponse schema."""
    student_name: Optional[str] = None
    course_name: Optional[str] = None
    if record.student:
        student_name = record.student.full_name
    if record.course:
        course_name = record.course.name
    return AttendanceResponse(
        id=record.id,
        student_id=record.student_id,
        course_id=record.course_id,
        teacher_id=record.teacher_id,
        date=record.date,
        status=record.status,
        note=record.note,
        notified_parent=record.notified_parent,
        created_at=record.created_at,
        updated_at=record.updated_at,
        student_name=student_name,
        course_name=course_name,
    )


class AttendanceService:
    """Encapsulates all attendance tracking logic."""

    def mark_attendance(
        self,
        teacher_id: int,
        student_id: int,
        course_id: int,
        record_date: date,
        status: AttendanceStatus,
        note: Optional[str],
        db: Session,
    ) -> AttendanceResponse:
        """Upsert a single attendance record."""
        existing = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.course_id == course_id,
                AttendanceRecord.date == record_date,
            )
            .first()
        )
        if existing:
            existing.status = status
            existing.note = note
            existing.teacher_id = teacher_id
            db.commit()
            db.refresh(existing)
            return _to_response(existing)
        else:
            record = AttendanceRecord(
                student_id=student_id,
                course_id=course_id,
                teacher_id=teacher_id,
                date=record_date,
                status=status,
                note=note,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return _to_response(record)

    def bulk_mark(
        self,
        teacher_id: int,
        course_id: int,
        record_date: date,
        records: list[BulkAttendanceEntry],
        db: Session,
    ) -> dict:
        """Bulk upsert attendance for a whole class on a given date."""
        created_count = 0
        updated_count = 0
        results: list[AttendanceResponse] = []

        for entry in records:
            existing = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.student_id == entry.student_id,
                    AttendanceRecord.course_id == course_id,
                    AttendanceRecord.date == record_date,
                )
                .first()
            )
            if existing:
                existing.status = entry.status
                existing.note = entry.note
                existing.teacher_id = teacher_id
                updated_count += 1
                db.flush()
                results.append(_to_response(existing))
            else:
                record = AttendanceRecord(
                    student_id=entry.student_id,
                    course_id=course_id,
                    teacher_id=teacher_id,
                    date=record_date,
                    status=entry.status,
                    note=entry.note,
                )
                db.add(record)
                created_count += 1
                db.flush()
                db.refresh(record)
                results.append(_to_response(record))

        db.commit()
        return {
            "created": created_count,
            "updated": updated_count,
            "records": results,
        }

    def get_course_attendance(
        self,
        course_id: int,
        record_date: date,
        db: Session,
    ) -> list[AttendanceResponse]:
        """Return all attendance records for a course on a specific date."""
        records = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.course_id == course_id,
                AttendanceRecord.date == record_date,
            )
            .all()
        )
        return [_to_response(r) for r in records]

    def get_student_summary(
        self,
        student_id: int,
        db: Session,
        course_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AttendanceSummary:
        """Return an attendance summary for a student, optionally filtered by course and date range."""
        query = db.query(AttendanceRecord).filter(AttendanceRecord.student_id == student_id)
        if course_id:
            query = query.filter(AttendanceRecord.course_id == course_id)
        if start_date:
            query = query.filter(AttendanceRecord.date >= start_date)
        if end_date:
            query = query.filter(AttendanceRecord.date <= end_date)

        records = query.all()

        present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        late = sum(1 for r in records if r.status == AttendanceStatus.LATE)
        excused = sum(1 for r in records if r.status == AttendanceStatus.EXCUSED)
        total = len(records)
        pct = round((present + late) / total * 100, 1) if total > 0 else 0.0

        # Resolve student name
        user = db.query(User).filter(User.id == student_id).first()
        student_name = user.full_name if user else f"Student {student_id}"

        course_name: Optional[str] = None
        if course_id:
            course = db.query(Course).filter(Course.id == course_id).first()
            if course:
                course_name = course.name

        return AttendanceSummary(
            student_id=student_id,
            student_name=student_name,
            course_id=course_id,
            course_name=course_name,
            present_count=present,
            absent_count=absent,
            late_count=late,
            excused_count=excused,
            total_days=total,
            attendance_pct=pct,
        )

    def get_course_report(
        self,
        course_id: int,
        start_date: date,
        end_date: date,
        db: Session,
    ) -> CourseAttendanceReport:
        """Return a full attendance report for a course within a date range."""
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            raise ValueError(f"Course {course_id} not found")

        # Get distinct student IDs that have records in the given window
        student_ids = (
            db.query(AttendanceRecord.student_id)
            .filter(
                AttendanceRecord.course_id == course_id,
                AttendanceRecord.date >= start_date,
                AttendanceRecord.date <= end_date,
            )
            .distinct()
            .all()
        )
        student_ids_list = [row[0] for row in student_ids]

        summaries = [
            self.get_student_summary(
                student_id=sid,
                db=db,
                course_id=course_id,
                start_date=start_date,
                end_date=end_date,
            )
            for sid in student_ids_list
        ]

        return CourseAttendanceReport(
            course_id=course_id,
            course_name=course.name,
            start_date=start_date,
            end_date=end_date,
            student_summaries=summaries,
        )

    def check_and_notify_absences(self, db: Session) -> int:
        """
        Check all students for 3+ consecutive absences (across all courses)
        and create Notification records for parents + AttendanceAlert records.

        Returns the number of new alerts created.
        """
        alerts_created = 0

        # Gather all students that have absence records
        student_course_pairs = (
            db.query(
                AttendanceRecord.student_id,
                AttendanceRecord.course_id,
            )
            .filter(AttendanceRecord.status == AttendanceStatus.ABSENT)
            .distinct()
            .all()
        )

        for student_id, course_id in student_course_pairs:
            # Fetch the last 7 consecutive dates with absence records, sorted descending
            recent_absences = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.student_id == student_id,
                    AttendanceRecord.course_id == course_id,
                    AttendanceRecord.status == AttendanceStatus.ABSENT,
                )
                .order_by(desc(AttendanceRecord.date))
                .limit(7)
                .all()
            )

            if len(recent_absences) < 3:
                continue

            # Check for 3 consecutive calendar days (ignoring weekends by day count)
            dates_sorted = sorted([r.date for r in recent_absences], reverse=True)
            consecutive = 1
            for i in range(1, len(dates_sorted)):
                delta = (dates_sorted[i - 1] - dates_sorted[i]).days
                if delta == 1:
                    consecutive += 1
                    if consecutive >= 3:
                        break
                else:
                    break

            if consecutive < 3:
                continue

            # Check if we already sent an alert for this pair recently (last 7 days)
            existing_alert = (
                db.query(AttendanceAlert)
                .filter(
                    AttendanceAlert.student_id == student_id,
                    AttendanceAlert.course_id == course_id,
                    AttendanceAlert.alert_sent_at >= datetime.utcnow() - timedelta(days=7),
                )
                .first()
            )
            if existing_alert:
                continue

            # Resolve parents for this student via parent_students join table
            parent_rows = (
                db.query(parent_students.c.parent_id)
                .filter(parent_students.c.student_id == student_id)
                .all()
            )

            # student_id here is a User.id — look up the Student record to resolve user FK
            student_record = db.query(Student).filter(Student.user_id == student_id).first()
            if student_record is None:
                # student_id may already be Student.id in some places; try by Student.id
                student_record = db.query(Student).filter(Student.id == student_id).first()

            if student_record:
                parent_rows = (
                    db.query(parent_students.c.parent_id)
                    .filter(parent_students.c.student_id == student_record.id)
                    .all()
                )

            student_user = db.query(User).filter(User.id == student_id).first()
            student_name = student_user.full_name if student_user else f"Student {student_id}"

            course = db.query(Course).filter(Course.id == course_id).first()
            course_name = course.name if course else f"Course {course_id}"

            for (parent_id,) in parent_rows:
                # Create notification for parent
                notification = Notification(
                    user_id=parent_id,
                    type=NotificationType.SYSTEM,
                    title=f"Attendance Alert: {student_name}",
                    content=(
                        f"{student_name} has been absent for {consecutive} consecutive "
                        f"day(s) in {course_name}. Please contact the school if needed."
                    ),
                    link="/attendance",
                )
                db.add(notification)

                # Create alert record
                alert = AttendanceAlert(
                    student_id=student_id,
                    parent_id=parent_id,
                    course_id=course_id,
                    consecutive_absences=consecutive,
                    alert_sent_at=datetime.utcnow(),
                )
                db.add(alert)
                alerts_created += 1

            # Mark records as having notified parent
            db.query(AttendanceRecord).filter(
                AttendanceRecord.student_id == student_id,
                AttendanceRecord.course_id == course_id,
                AttendanceRecord.status == AttendanceStatus.ABSENT,
                AttendanceRecord.notified_parent == False,  # noqa: E712
            ).update({"notified_parent": True})

        db.commit()
        return alerts_created

    def get_parent_child_attendance(
        self,
        parent_id: int,
        student_id: int,
        db: Session,
    ) -> AttendanceSummary:
        """
        Return attendance summary for a parent's child.
        Verifies the parent-child relationship before returning data.
        """
        # Verify the parent has a linked student with this user_id
        student_record = db.query(Student).filter(Student.user_id == student_id).first()
        if not student_record:
            raise ValueError(f"No student profile found for user {student_id}")

        link = (
            db.query(parent_students)
            .filter(
                parent_students.c.parent_id == parent_id,
                parent_students.c.student_id == student_record.id,
            )
            .first()
        )
        if not link:
            raise PermissionError("Parent is not linked to this student")

        return self.get_student_summary(student_id=student_id, db=db)
