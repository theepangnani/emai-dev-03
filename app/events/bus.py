"""
Event bus for synchronous in-process domain event dispatch.

Call `register_default_handlers()` from main.py startup to wire up
all default cross-context handlers.
"""
import asyncio
import logging
from typing import Callable, Any
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DomainEvent:
    """Base class for all domain events."""
    event_type: str
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    user_id: int | None = None
    metadata: dict = field(default_factory=dict)


class EventBus:
    """
    Synchronous in-process event bus.

    Features:
    - Subscribe handlers to event types
    - Publish events synchronously (all handlers called immediately)
    - Async handler support (runs in event loop if available)
    - Handler errors are caught and logged (don't propagate)
    - Wildcard subscription with "*"
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable]] = defaultdict(list)
        self._event_log: list[DomainEvent] = []  # last 1000 events in memory
        self._max_log_size = 1000

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """Register a handler for an event type. Use "*" for all events."""
        self._handlers[event_type].append(handler)
        logger.debug(f"Subscribed {handler.__name__} to {event_type}")

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """Remove a handler."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    def publish(self, event: DomainEvent) -> None:
        """
        Publish an event synchronously.
        Calls all handlers for the event_type and wildcard handlers.
        Errors in handlers are caught and logged.
        """
        self._log_event(event)
        handlers = (
            list(self._handlers.get(event.event_type, []))
            + list(self._handlers.get("*", []))
        )

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    # Run async handler in current event loop if available
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.ensure_future(handler(event))
                        else:
                            loop.run_until_complete(handler(event))
                    except RuntimeError:
                        # No event loop — create one
                        asyncio.run(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(
                    f"Event handler {handler.__name__} failed for "
                    f"{event.event_type}: {e}"
                )

    def _log_event(self, event: DomainEvent) -> None:
        self._event_log.append(event)
        if len(self._event_log) > self._max_log_size:
            self._event_log = self._event_log[-self._max_log_size:]

    def get_recent_events(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[DomainEvent]:
        """Get recent events for debugging/admin."""
        events = self._event_log[-limit:]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events


# Global singleton
_event_bus = EventBus()


def get_event_bus() -> EventBus:
    return _event_bus
