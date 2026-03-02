"""
Typed domain events for the EMAI ClassBridge platform.

Each event is a dataclass that extends DomainEvent, adding domain-specific
fields. The event_type string is used by the EventBus to dispatch to handlers.
"""
from dataclasses import dataclass, field
from app.events.bus import DomainEvent


# ── Study Events ─────────────────────────────────────────────────────────────

@dataclass
class StudyGuideGeneratedEvent(DomainEvent):
    event_type: str = "study_guide.generated"
    study_guide_id: int = 0
    course_id: int | None = None
    word_count: int = 0
    is_duplicate: bool = False


@dataclass
class QuizAttemptCompletedEvent(DomainEvent):
    event_type: str = "quiz.attempt_completed"
    study_guide_id: int = 0
    score: float = 0.0
    passed: bool = False
    subject_code: str = ""


@dataclass
class FlashcardStudiedEvent(DomainEvent):
    event_type: str = "flashcard.studied"
    study_guide_id: int = 0
    cards_studied: int = 0


# ── Assignment Events ─────────────────────────────────────────────────────────

@dataclass
class AssignmentSubmittedEvent(DomainEvent):
    event_type: str = "assignment.submitted"
    assignment_id: int = 0
    student_id: int = 0
    course_id: int = 0


@dataclass
class AssignmentDueSoonEvent(DomainEvent):
    event_type: str = "assignment.due_soon"
    assignment_id: int = 0
    hours_until_due: float = 0.0


# ── Messaging Events ──────────────────────────────────────────────────────────

@dataclass
class MessageSentEvent(DomainEvent):
    event_type: str = "message.sent"
    conversation_id: int = 0
    recipient_user_id: int = 0


@dataclass
class EmailThreadReplyReceivedEvent(DomainEvent):
    event_type: str = "email.reply_received"
    thread_id: int = 0
    from_email: str = ""


# ── User Events ───────────────────────────────────────────────────────────────

@dataclass
class UserRegisteredEvent(DomainEvent):
    event_type: str = "user.registered"
    role: str = ""
    invited_by_user_id: int | None = None


@dataclass
class UserSubscriptionChangedEvent(DomainEvent):
    event_type: str = "subscription.changed"
    old_tier: str = "free"
    new_tier: str = "premium"
    stripe_subscription_id: str = ""


@dataclass
class StudyStreakUpdatedEvent(DomainEvent):
    event_type: str = "streak.updated"
    student_id: int = 0
    new_streak_days: int = 0
    is_at_risk: bool = False


# ── Booking Events ────────────────────────────────────────────────────────────

@dataclass
class TutorBookingRequestedEvent(DomainEvent):
    event_type: str = "tutor_booking.requested"
    booking_id: int = 0
    tutor_user_id: int = 0
    student_user_id: int = 0


@dataclass
class TutorBookingAcceptedEvent(DomainEvent):
    event_type: str = "tutor_booking.accepted"
    booking_id: int = 0


# ── LMS Events ────────────────────────────────────────────────────────────────

@dataclass
class LMSSyncCompletedEvent(DomainEvent):
    event_type: str = "lms.sync_completed"
    provider: str = ""
    courses_synced: int = 0
    assignments_synced: int = 0


# ── Public API ────────────────────────────────────────────────────────────────

__all__ = [
    "StudyGuideGeneratedEvent",
    "QuizAttemptCompletedEvent",
    "FlashcardStudiedEvent",
    "AssignmentSubmittedEvent",
    "AssignmentDueSoonEvent",
    "MessageSentEvent",
    "EmailThreadReplyReceivedEvent",
    "UserRegisteredEvent",
    "UserSubscriptionChangedEvent",
    "StudyStreakUpdatedEvent",
    "TutorBookingRequestedEvent",
    "TutorBookingAcceptedEvent",
    "LMSSyncCompletedEvent",
]
