"""
Default event handlers that wire up cross-context reactions.
Register these in the event bus at startup.

# Call this from main.py startup:
#   from app.events.handlers import register_default_handlers
#   register_default_handlers()
"""
import logging
import os

from app.events.bus import DomainEvent, get_event_bus
from app.events.types import (
    QuizAttemptCompletedEvent,
    StudyGuideGeneratedEvent,
    UserSubscriptionChangedEvent,
    TutorBookingRequestedEvent,
    TutorBookingAcceptedEvent,
    StudyStreakUpdatedEvent,
)

logger = logging.getLogger(__name__)


def on_quiz_completed(event: QuizAttemptCompletedEvent) -> None:
    """
    When a quiz is completed:
    - Trigger mastery score recomputation (lazy — just invalidate cache)
    - Update adaptive difficulty
    """
    logger.info(
        f"Quiz completed: user={event.user_id}, "
        f"score={event.score:.0%}, subject={event.subject_code}"
    )
    # Invalidation hook — actual recompute is lazy on next API call
    # Future: publish to personalization service


def on_subscription_changed(event: UserSubscriptionChangedEvent) -> None:
    """When user upgrades to premium, log and hook for post-upgrade onboarding."""
    logger.info(
        f"Subscription changed: user={event.user_id} "
        f"{event.old_tier}\u2192{event.new_tier}"
    )


def on_tutor_booking_requested(event: TutorBookingRequestedEvent) -> None:
    """When a booking is requested, log for notification system."""
    logger.info(
        f"Tutor booking requested: booking={event.booking_id}, "
        f"tutor={event.tutor_user_id}"
    )


def on_streak_at_risk(event: StudyStreakUpdatedEvent) -> None:
    """When streak is at risk, log for notification."""
    if event.is_at_risk:
        logger.info(
            f"Streak at risk: student={event.student_id}, "
            f"streak={event.new_streak_days}"
        )


def on_wildcard(event: DomainEvent) -> None:
    """Debug handler that logs all events (only in DEBUG mode)."""
    logger.debug(f"Event: {event.event_type} user={event.user_id}")


def register_default_handlers() -> None:
    """
    Register all default handlers with the global event bus.

    Call this from main.py startup:
        from app.events.handlers import register_default_handlers
        register_default_handlers()
    """
    bus = get_event_bus()
    bus.subscribe("quiz.attempt_completed", on_quiz_completed)
    bus.subscribe("subscription.changed", on_subscription_changed)
    bus.subscribe("tutor_booking.requested", on_tutor_booking_requested)
    bus.subscribe("streak.updated", on_streak_at_risk)

    # Debug wildcard — only in DEBUG mode to avoid log noise in production
    if os.getenv("LOG_LEVEL", "").upper() == "DEBUG":
        bus.subscribe("*", on_wildcard)
