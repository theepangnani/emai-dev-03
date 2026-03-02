"""Domain Events package."""
from app.events.bus import EventBus, get_event_bus, DomainEvent
from app.events.types import (
    StudyGuideGeneratedEvent,
    QuizAttemptCompletedEvent,
    FlashcardStudiedEvent,
    AssignmentSubmittedEvent,
    AssignmentDueSoonEvent,
    MessageSentEvent,
    EmailThreadReplyReceivedEvent,
    UserRegisteredEvent,
    UserSubscriptionChangedEvent,
    StudyStreakUpdatedEvent,
    TutorBookingRequestedEvent,
    TutorBookingAcceptedEvent,
    LMSSyncCompletedEvent,
)

__all__ = [
    "EventBus",
    "get_event_bus",
    "DomainEvent",
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
