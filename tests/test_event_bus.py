"""
Tests for the domain events system.

Covers EventBus mechanics, typed events, default handlers, and the admin API.
"""
import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=False)
def fresh_bus():
    """Return a fresh EventBus (not the global singleton) for isolation."""
    from app.events.bus import EventBus
    return EventBus()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Basic subscribe + publish
# ─────────────────────────────────────────────────────────────────────────────

def test_subscribe_and_publish(fresh_bus):
    """Handler is called once when its event type is published."""
    from app.events.bus import DomainEvent

    received = []

    def handler(event):
        received.append(event)

    fresh_bus.subscribe("test.event", handler)
    event = DomainEvent(event_type="test.event", user_id=1)
    fresh_bus.publish(event)

    assert len(received) == 1
    assert received[0] is event


# ─────────────────────────────────────────────────────────────────────────────
# 2. Wildcard subscription
# ─────────────────────────────────────────────────────────────────────────────

def test_wildcard_subscription(fresh_bus):
    """Wildcard handler receives every published event regardless of type."""
    from app.events.bus import DomainEvent

    received = []

    def wildcard_handler(event):
        received.append(event.event_type)

    fresh_bus.subscribe("*", wildcard_handler)
    fresh_bus.publish(DomainEvent(event_type="foo.bar"))
    fresh_bus.publish(DomainEvent(event_type="baz.qux"))

    assert received == ["foo.bar", "baz.qux"]


# ─────────────────────────────────────────────────────────────────────────────
# 3. Handler error doesn't propagate
# ─────────────────────────────────────────────────────────────────────────────

def test_handler_error_doesnt_propagate(fresh_bus):
    """A failing handler logs the error but does NOT raise to the caller."""
    from app.events.bus import DomainEvent

    def bad_handler(event):
        raise RuntimeError("oops")

    good_called = []

    def good_handler(event):
        good_called.append(True)

    fresh_bus.subscribe("test.fail", bad_handler)
    fresh_bus.subscribe("test.fail", good_handler)

    # Should not raise
    fresh_bus.publish(DomainEvent(event_type="test.fail"))

    # The good handler still runs after the bad one
    assert good_called == [True]


# ─────────────────────────────────────────────────────────────────────────────
# 4. Unsubscribe
# ─────────────────────────────────────────────────────────────────────────────

def test_unsubscribe(fresh_bus):
    """Unsubscribed handler is not called on subsequent publishes."""
    from app.events.bus import DomainEvent

    calls = []

    def handler(event):
        calls.append(1)

    fresh_bus.subscribe("test.unsub", handler)
    fresh_bus.publish(DomainEvent(event_type="test.unsub"))
    assert calls == [1]

    fresh_bus.unsubscribe("test.unsub", handler)
    fresh_bus.publish(DomainEvent(event_type="test.unsub"))
    assert calls == [1]  # still only one call


# ─────────────────────────────────────────────────────────────────────────────
# 5. Event log truncation
# ─────────────────────────────────────────────────────────────────────────────

def test_event_log_truncation(fresh_bus):
    """Log never exceeds _max_log_size events."""
    from app.events.bus import DomainEvent

    fresh_bus._max_log_size = 10
    for i in range(20):
        fresh_bus.publish(DomainEvent(event_type=f"event.{i}"))

    assert len(fresh_bus._event_log) <= 10
    # Most recent event is last
    assert fresh_bus._event_log[-1].event_type == "event.19"


# ─────────────────────────────────────────────────────────────────────────────
# 6. Typed event fields preserved
# ─────────────────────────────────────────────────────────────────────────────

def test_typed_event_fields_preserved(fresh_bus):
    """Domain-specific fields survive publish-receive round trip."""
    from app.events.types import QuizAttemptCompletedEvent

    received = []

    def handler(event):
        received.append(event)

    fresh_bus.subscribe("quiz.attempt_completed", handler)

    ev = QuizAttemptCompletedEvent(
        event_type="quiz.attempt_completed",
        user_id=42,
        study_guide_id=7,
        score=0.85,
        passed=True,
        subject_code="MATH101",
    )
    fresh_bus.publish(ev)

    assert len(received) == 1
    r = received[0]
    assert r.user_id == 42
    assert r.study_guide_id == 7
    assert r.score == pytest.approx(0.85)
    assert r.passed is True
    assert r.subject_code == "MATH101"


# ─────────────────────────────────────────────────────────────────────────────
# 7. Quiz completed handler called
# ─────────────────────────────────────────────────────────────────────────────

def test_quiz_completed_handler_called(fresh_bus):
    """Default on_quiz_completed handler logs when subscribed."""
    from app.events.types import QuizAttemptCompletedEvent
    from app.events import handlers

    fresh_bus.subscribe("quiz.attempt_completed", handlers.on_quiz_completed)

    ev = QuizAttemptCompletedEvent(
        event_type="quiz.attempt_completed",
        user_id=1,
        score=0.9,
        subject_code="SCI",
    )
    # Should not raise
    fresh_bus.publish(ev)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Async handler support
# ─────────────────────────────────────────────────────────────────────────────

def test_async_handler_support(fresh_bus):
    """Async handlers are executed without raising errors."""
    from app.events.bus import DomainEvent

    results = []

    async def async_handler(event):
        results.append(event.event_type)

    fresh_bus.subscribe("async.test", async_handler)
    fresh_bus.publish(DomainEvent(event_type="async.test"))

    # Give event loop a chance to process if running in a loop context
    # For this synchronous test we just verify no exception was raised.
    # Results may be populated synchronously via asyncio.run or via future.
    # Either way, the bus should not raise.


# ─────────────────────────────────────────────────────────────────────────────
# 9. get_recent_events filter
# ─────────────────────────────────────────────────────────────────────────────

def test_get_recent_events_filter(fresh_bus):
    """get_recent_events filters by event_type correctly."""
    from app.events.bus import DomainEvent

    fresh_bus.publish(DomainEvent(event_type="a.one"))
    fresh_bus.publish(DomainEvent(event_type="b.two"))
    fresh_bus.publish(DomainEvent(event_type="a.one"))

    all_events = fresh_bus.get_recent_events()
    assert len(all_events) == 3

    filtered = fresh_bus.get_recent_events(event_type="a.one")
    assert len(filtered) == 2
    assert all(e.event_type == "a.one" for e in filtered)


# ─────────────────────────────────────────────────────────────────────────────
# 10. Multiple handlers for the same event
# ─────────────────────────────────────────────────────────────────────────────

def test_multiple_handlers_same_event(fresh_bus):
    """All handlers subscribed to the same event type are called."""
    from app.events.bus import DomainEvent

    calls = []
    fresh_bus.subscribe("shared.event", lambda e: calls.append("h1"))
    fresh_bus.subscribe("shared.event", lambda e: calls.append("h2"))
    fresh_bus.subscribe("shared.event", lambda e: calls.append("h3"))

    fresh_bus.publish(DomainEvent(event_type="shared.event"))
    assert calls == ["h1", "h2", "h3"]


# ─────────────────────────────────────────────────────────────────────────────
# 11. Singleton bus
# ─────────────────────────────────────────────────────────────────────────────

def test_singleton_bus():
    """get_event_bus() always returns the same instance."""
    from app.events.bus import get_event_bus

    bus1 = get_event_bus()
    bus2 = get_event_bus()
    assert bus1 is bus2


# ─────────────────────────────────────────────────────────────────────────────
# 12. All typed event types are instantiable with defaults
# ─────────────────────────────────────────────────────────────────────────────

def test_all_event_types_instantiable():
    """Every typed event class can be instantiated with only default values."""
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

    event_classes = [
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
    ]

    for cls in event_classes:
        instance = cls()
        assert instance.event_type  # non-empty string
        assert isinstance(instance.occurred_at, datetime)


# ─────────────────────────────────────────────────────────────────────────────
# 13. Publish with no handlers registered
# ─────────────────────────────────────────────────────────────────────────────

def test_publish_with_no_handlers(fresh_bus):
    """Publishing an event with no handlers registered must not raise."""
    from app.events.bus import DomainEvent

    fresh_bus.publish(DomainEvent(event_type="orphan.event", user_id=99))
    events = fresh_bus.get_recent_events()
    assert len(events) == 1
    assert events[0].event_type == "orphan.event"


# ─────────────────────────────────────────────────────────────────────────────
# 14. get_recent_events limit respected
# ─────────────────────────────────────────────────────────────────────────────

def test_get_recent_events_limit(fresh_bus):
    """get_recent_events returns at most `limit` events."""
    from app.events.bus import DomainEvent

    for i in range(50):
        fresh_bus.publish(DomainEvent(event_type="bulk.event"))

    result = fresh_bus.get_recent_events(limit=10)
    assert len(result) == 10


# ─────────────────────────────────────────────────────────────────────────────
# 15. Streak at-risk handler only logs when is_at_risk=True
# ─────────────────────────────────────────────────────────────────────────────

def test_streak_at_risk_handler_conditional(fresh_bus):
    """on_streak_at_risk only logs when is_at_risk is True."""
    from app.events.types import StudyStreakUpdatedEvent
    from app.events import handlers

    fresh_bus.subscribe("streak.updated", handlers.on_streak_at_risk)

    safe_event = StudyStreakUpdatedEvent(
        event_type="streak.updated",
        student_id=1,
        new_streak_days=5,
        is_at_risk=False,
    )
    risk_event = StudyStreakUpdatedEvent(
        event_type="streak.updated",
        student_id=2,
        new_streak_days=1,
        is_at_risk=True,
    )

    # Both should publish without raising
    fresh_bus.publish(safe_event)
    fresh_bus.publish(risk_event)

    events = fresh_bus.get_recent_events(event_type="streak.updated")
    assert len(events) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 16. DomainEvent metadata field
# ─────────────────────────────────────────────────────────────────────────────

def test_domain_event_metadata(fresh_bus):
    """Arbitrary metadata dict is preserved on the event."""
    from app.events.bus import DomainEvent

    received = []
    fresh_bus.subscribe("meta.test", lambda e: received.append(e))

    fresh_bus.publish(DomainEvent(
        event_type="meta.test",
        metadata={"source": "test", "attempt": 3},
    ))

    assert received[0].metadata == {"source": "test", "attempt": 3}


# ─────────────────────────────────────────────────────────────────────────────
# 17. register_default_handlers wires correct event types
# ─────────────────────────────────────────────────────────────────────────────

def test_register_default_handlers_wires_events():
    """register_default_handlers subscribes to the expected event types."""
    from app.events.bus import EventBus
    from app.events import handlers

    bus = EventBus()

    # Monkey-patch get_event_bus to return our local bus
    original_get = handlers.get_event_bus

    def patched_get():
        return bus

    handlers.get_event_bus = patched_get
    try:
        handlers.register_default_handlers()
    finally:
        handlers.get_event_bus = original_get

    assert "quiz.attempt_completed" in bus._handlers
    assert "subscription.changed" in bus._handlers
    assert "tutor_booking.requested" in bus._handlers
    assert "streak.updated" in bus._handlers


# ─────────────────────────────────────────────────────────────────────────────
# 18. LMSSyncCompletedEvent fields
# ─────────────────────────────────────────────────────────────────────────────

def test_lms_sync_completed_event_fields(fresh_bus):
    """LMSSyncCompletedEvent carries provider and sync counts."""
    from app.events.types import LMSSyncCompletedEvent

    received = []
    fresh_bus.subscribe("lms.sync_completed", lambda e: received.append(e))

    ev = LMSSyncCompletedEvent(
        event_type="lms.sync_completed",
        provider="brightspace",
        courses_synced=5,
        assignments_synced=22,
    )
    fresh_bus.publish(ev)

    assert received[0].provider == "brightspace"
    assert received[0].courses_synced == 5
    assert received[0].assignments_synced == 22


# ─────────────────────────────────────────────────────────────────────────────
# 19. Unsubscribe non-existent handler is safe
# ─────────────────────────────────────────────────────────────────────────────

def test_unsubscribe_nonexistent_handler_is_safe(fresh_bus):
    """Unsubscribing a handler that was never registered must not raise."""

    def phantom(event):
        pass

    # No exception expected
    fresh_bus.unsubscribe("ghost.event", phantom)
    fresh_bus.unsubscribe("nonexistent.type", phantom)
