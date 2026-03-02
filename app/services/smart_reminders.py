"""SmartReminderService — AI-prioritized, multi-stage reminder engine.

Stages:
  LOW      — 3+ days before due
  MEDIUM   — ~1 day before due
  HIGH     — ~3 hours before due
  CRITICAL — past due (up to 7 days)

Features:
  - Priority scoring (max_points, urgency multiplier, mastery gap bonus)
  - AI-generated personalized messages via GPT-4o-mini
  - Dedup via ReminderLog unique constraint (user, assignment, urgency)
  - Parent escalation when assignment is overdue beyond preference threshold
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.assignment import Assignment
from app.models.course import student_courses
from app.models.notification import Notification, NotificationType
from app.models.smart_reminder import ReminderLog, ReminderPreference, ReminderUrgency
from app.models.student import Student, parent_students
from app.models.user import User

logger = logging.getLogger(__name__)

# Time windows (hours before due) for each urgency level
_URGENCY_WINDOWS = {
    ReminderUrgency.LOW: (48, 96),        # 2–4 days out → send "3 days" reminder
    ReminderUrgency.MEDIUM: (18, 48),     # 18–48 hours out → send "1 day" reminder
    ReminderUrgency.HIGH: (1, 18),        # 1–18 hours out → send "3 hours" reminder
    ReminderUrgency.CRITICAL: (-168, 0),  # past due, up to 7 days (negative hours)
}

# Urgency multipliers for priority scoring
_URGENCY_MULTIPLIERS = {
    ReminderUrgency.LOW: 1.0,
    ReminderUrgency.MEDIUM: 1.5,
    ReminderUrgency.HIGH: 2.0,
    ReminderUrgency.CRITICAL: 3.0,
}

# Template messages (used when AI is disabled or unavailable)
_TEMPLATES = {
    ReminderUrgency.LOW: "Hey {name}, just a heads-up — '{title}' is due in about 3 days. Get started early!",
    ReminderUrgency.MEDIUM: "Reminder, {name}: '{title}' is due tomorrow. Make sure you're on track!",
    ReminderUrgency.HIGH: "Urgent reminder, {name}: '{title}' is due in just a few hours. Finish up now!",
    ReminderUrgency.CRITICAL: "Action needed, {name}: '{title}' is now overdue. Submit as soon as possible.",
}


class SmartReminderService:
    """Core service for calculating, generating, and dispatching smart reminders."""

    def calculate_priority_score(
        self,
        assignment: Assignment,
        urgency: ReminderUrgency,
        student_has_mastery_gap: bool = False,
    ) -> float:
        """Return a 0–10 priority score for this (assignment, urgency) pair.

        Formula:
          base  = max_points * 0.3  (high-stakes assignments scored more urgently)
          score = base * urgency_multiplier
          bonus = +0.5 if student has a mastery gap in this course
          cap   = 10.0
        """
        max_points = assignment.max_points or 10.0  # default 10 if unset
        base = max_points * 0.3
        multiplier = _URGENCY_MULTIPLIERS.get(urgency, 1.0)
        score = base * multiplier
        if student_has_mastery_gap:
            score += 0.5
        return min(round(score, 2), 10.0)

    def _classify_urgency(self, assignment: Assignment, now: datetime) -> Optional[ReminderUrgency]:
        """Determine which urgency bucket this assignment falls into, or None if outside all windows."""
        if not assignment.due_date:
            return None

        due = assignment.due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)

        hours_until_due = (due - now).total_seconds() / 3600.0

        if -168 <= hours_until_due < 0:
            return ReminderUrgency.CRITICAL
        if 1 <= hours_until_due < 18:
            return ReminderUrgency.HIGH
        if 18 <= hours_until_due < 48:
            return ReminderUrgency.MEDIUM
        if 48 <= hours_until_due < 96:
            return ReminderUrgency.LOW
        return None

    def _is_urgency_enabled(self, prefs: Optional[ReminderPreference], urgency: ReminderUrgency) -> bool:
        """Return True if the user's preferences allow sending at this urgency level."""
        if prefs is None:
            return True  # default: all enabled
        mapping = {
            ReminderUrgency.LOW: prefs.remind_3_days,
            ReminderUrgency.MEDIUM: prefs.remind_1_day,
            ReminderUrgency.HIGH: prefs.remind_3_hours,
            ReminderUrgency.CRITICAL: prefs.remind_overdue,
        }
        return mapping.get(urgency, True)

    def generate_reminder_message(
        self,
        assignment: Assignment,
        urgency: ReminderUrgency,
        student_name: str,
        ai_personalized: bool = True,
    ) -> str:
        """Generate a reminder message.

        If ai_personalized=True, calls GPT-4o-mini for a 1-2 sentence personalized message.
        Falls back to a template on any error or if ai_personalized=False.
        """
        if ai_personalized:
            try:
                return self._generate_ai_message(assignment, urgency, student_name)
            except Exception as exc:
                logger.warning(f"AI reminder generation failed, using template | error={exc}")

        template = _TEMPLATES.get(urgency, _TEMPLATES[ReminderUrgency.MEDIUM])
        return template.format(name=student_name, title=assignment.title)

    def _generate_ai_message(
        self,
        assignment: Assignment,
        urgency: ReminderUrgency,
        student_name: str,
    ) -> str:
        """Call GPT-4o-mini to produce a short, personalized reminder."""
        from openai import OpenAI
        from app.core.config import settings

        client = OpenAI(api_key=settings.openai_api_key)

        urgency_context = {
            ReminderUrgency.LOW: "The assignment is due in about 3 days.",
            ReminderUrgency.MEDIUM: "The assignment is due tomorrow.",
            ReminderUrgency.HIGH: "The assignment is due in just a few hours.",
            ReminderUrgency.CRITICAL: "The assignment is now past due.",
        }[urgency]

        due_str = (
            assignment.due_date.strftime("%B %d at %I:%M %p")
            if assignment.due_date
            else "soon"
        )

        prompt = (
            f"Write a 1-2 sentence friendly but urgent reminder for a student named {student_name}. "
            f"Assignment: '{assignment.title}'. Due: {due_str}. {urgency_context} "
            f"Be encouraging, not alarming. Do not use emojis."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    def _already_sent(
        self,
        db: Session,
        user_id: int,
        assignment_id: int,
        urgency: ReminderUrgency,
    ) -> bool:
        """Return True if a reminder at this urgency was already logged for (user, assignment)."""
        existing = (
            db.query(ReminderLog.id)
            .filter(
                ReminderLog.user_id == user_id,
                ReminderLog.assignment_id == assignment_id,
                ReminderLog.urgency == urgency,
            )
            .first()
        )
        return existing is not None

    def _get_preferences(self, db: Session, user_id: int) -> Optional[ReminderPreference]:
        return (
            db.query(ReminderPreference)
            .filter(ReminderPreference.user_id == user_id)
            .first()
        )

    def _has_mastery_gap(self, db: Session, student: Student, course_id: int) -> bool:
        """Return True if the student has low mastery (<60) for this course's subject."""
        try:
            from app.models.personalization import SubjectMastery
            from app.models.course import Course

            course = db.query(Course).filter(Course.id == course_id).first()
            if not course:
                return False
            mastery = (
                db.query(SubjectMastery)
                .filter(
                    SubjectMastery.student_id == student.id,
                    SubjectMastery.mastery_score < 60,
                )
                .first()
            )
            return mastery is not None
        except Exception:
            return False

    def get_pending_reminders(
        self, db: Session
    ) -> list[tuple[Assignment, Student, User, ReminderUrgency]]:
        """Return all (assignment, student, student_user, urgency) tuples that need a reminder.

        Queries assignments due within the next 4 days or up to 7 days past due.
        Excludes pairs where a ReminderLog already exists for that urgency level.
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=7)   # overdue up to 7 days ago
        window_end = now + timedelta(days=4)     # up to 4 days in the future

        # Get all assignments in the window
        assignments = (
            db.query(Assignment)
            .filter(
                Assignment.due_date >= window_start,
                Assignment.due_date <= window_end,
            )
            .all()
        )

        pending: list[tuple[Assignment, Student, User, ReminderUrgency]] = []

        for assignment in assignments:
            urgency = self._classify_urgency(assignment, now)
            if urgency is None:
                continue

            # Find all students enrolled in this course
            student_ids_rows = (
                db.query(student_courses.c.student_id)
                .filter(student_courses.c.course_id == assignment.course_id)
                .all()
            )
            student_ids = [r[0] for r in student_ids_rows]

            for student_id in student_ids:
                student = db.query(Student).filter(Student.id == student_id).first()
                if not student:
                    continue
                student_user = db.query(User).filter(User.id == student.user_id).first()
                if not student_user or not student_user.is_active:
                    continue

                prefs = self._get_preferences(db, student_user.id)

                if not self._is_urgency_enabled(prefs, urgency):
                    continue

                if self._already_sent(db, student_user.id, assignment.id, urgency):
                    continue

                pending.append((assignment, student, student_user, urgency))

        return pending

    def send_reminder(
        self,
        assignment: Assignment,
        student: Student,
        student_user: User,
        urgency: ReminderUrgency,
        db: Session,
    ) -> None:
        """Calculate score, generate message, create Notification, log to ReminderLog, escalate to parent if needed."""
        prefs = self._get_preferences(db, student_user.id)
        ai_enabled = prefs.ai_personalized_messages if prefs else True

        mastery_gap = self._has_mastery_gap(db, student, assignment.course_id)
        priority_score = self.calculate_priority_score(assignment, urgency, mastery_gap)

        message = self.generate_reminder_message(
            assignment, urgency, student_user.full_name or "Student", ai_enabled
        )

        # Create in-app notification for student
        notification = Notification(
            user_id=student_user.id,
            type=NotificationType.ASSIGNMENT_DUE,
            title=self._build_title(assignment, urgency),
            content=message,
            link="/dashboard",
            source_type="assignment",
            source_id=assignment.id,
        )
        db.add(notification)

        # Log to ReminderLog (dedup guard)
        log_entry = ReminderLog(
            user_id=student_user.id,
            assignment_id=assignment.id,
            urgency=urgency,
            message=message,
            channel="in_app",
            priority_score=priority_score,
        )
        db.add(log_entry)

        try:
            db.flush()
        except Exception as exc:
            # UniqueConstraint violation = already sent (race condition) — safe to skip
            logger.debug(f"Reminder already logged (skipping) | {exc}")
            db.rollback()
            return

        # Parent escalation for overdue items
        if urgency == ReminderUrgency.CRITICAL:
            self._maybe_escalate_to_parent(assignment, student, student_user, prefs, message, db)

        db.commit()
        logger.info(
            f"Smart reminder sent | user={student_user.id} assignment={assignment.id} "
            f"urgency={urgency} score={priority_score}"
        )

    def _build_title(self, assignment: Assignment, urgency: ReminderUrgency) -> str:
        titles = {
            ReminderUrgency.LOW: f"{assignment.title} — due in 3 days",
            ReminderUrgency.MEDIUM: f"{assignment.title} — due tomorrow",
            ReminderUrgency.HIGH: f"{assignment.title} — due in a few hours",
            ReminderUrgency.CRITICAL: f"Overdue: {assignment.title}",
        }
        return titles.get(urgency, assignment.title)

    def _maybe_escalate_to_parent(
        self,
        assignment: Assignment,
        student: Student,
        student_user: User,
        prefs: Optional[ReminderPreference],
        student_message: str,
        db: Session,
    ) -> None:
        """Notify linked parents if overdue threshold exceeded."""
        if prefs is None:
            escalation_hours = 24
        else:
            escalation_hours = prefs.parent_escalation_hours

        if escalation_hours == 0:
            return  # escalation disabled

        if not assignment.due_date:
            return

        now = datetime.now(timezone.utc)
        due = assignment.due_date
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)

        hours_overdue = (now - due).total_seconds() / 3600.0
        if hours_overdue < escalation_hours:
            return

        # Fetch linked parents
        parent_rows = (
            db.query(parent_students)
            .filter(parent_students.c.student_id == student.id)
            .all()
        )
        for row in parent_rows:
            parent = db.query(User).filter(User.id == row.parent_id).first()
            if not parent or not parent.is_active:
                continue

            # Avoid duplicate parent escalation — check if we already sent a CRITICAL to parent for this assignment
            if self._already_sent(db, parent.id, assignment.id, ReminderUrgency.CRITICAL):
                continue

            parent_message = (
                f"Your child {student_user.full_name} has an overdue assignment: "
                f"'{assignment.title}'. It was due {int(hours_overdue)} hours ago."
            )
            parent_notif = Notification(
                user_id=parent.id,
                type=NotificationType.ASSIGNMENT_DUE,
                title=f"Overdue alert: {assignment.title}",
                content=parent_message,
                link="/dashboard",
                source_type="assignment",
                source_id=assignment.id,
            )
            db.add(parent_notif)

            parent_log = ReminderLog(
                user_id=parent.id,
                assignment_id=assignment.id,
                urgency=ReminderUrgency.CRITICAL,
                message=parent_message,
                channel="in_app",
                priority_score=None,
            )
            db.add(parent_log)
            logger.info(
                f"Parent escalation | parent={parent.id} student={student.id} assignment={assignment.id}"
            )

    def run_smart_reminders(self, db: Session) -> dict:
        """Main entry point — called by the APScheduler job.

        Returns a summary dict: {sent: int, skipped: int, errors: int}.
        """
        logger.info("Smart reminder job starting...")
        sent = 0
        skipped = 0
        errors = 0

        try:
            pending = self.get_pending_reminders(db)
            logger.info(f"Smart reminders: {len(pending)} pending reminder(s) found")

            for assignment, student, student_user, urgency in pending:
                try:
                    self.send_reminder(assignment, student, student_user, urgency, db)
                    sent += 1
                except Exception as exc:
                    errors += 1
                    logger.error(
                        f"Failed to send smart reminder | user={student_user.id} "
                        f"assignment={assignment.id} error={exc}",
                        exc_info=True,
                    )
                    db.rollback()

        except Exception as exc:
            logger.error(f"Smart reminder job failed | error={exc}", exc_info=True)
            db.rollback()

        logger.info(
            f"Smart reminder job complete | sent={sent} skipped={skipped} errors={errors}"
        )
        return {"sent": sent, "skipped": skipped, "errors": errors}
