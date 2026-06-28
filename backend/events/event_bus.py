"""
Event Bus for CSS Enterprise Event Bus

Handles pub/sub subscription mapping and synchronous execution of callbacks.
It guarantees:
- Safe exception isolation: errors in one subscriber don't prevent others from running.
- Deterministic delivery order based on subscription registration order.
- Thread-safe modifications to subscribers list.
"""

import logging
import threading
from typing import Dict, List, Callable, Optional
from backend.events.event_models import Event
from backend.events.event_metrics import EventMetrics

logger = logging.getLogger("css.events.event_bus")

class EventBus:
    def __init__(self, metrics: Optional[EventMetrics] = None):
        self._lock = threading.Lock()
        # Maps event_type -> list of subscribers
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = {}
        # Wildcard subscribers that receive all events
        self._wildcard_subscribers: List[Callable[[Event], None]] = []
        self._metrics = metrics

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """
        Subscribe a callback to a specific event type.
        Use event_type="*" to receive all published events.
        """
        with self._lock:
            if event_type == "*":
                if callback not in self._wildcard_subscribers:
                    self._wildcard_subscribers.append(callback)
            else:
                if event_type not in self._subscribers:
                    self._subscribers[event_type] = []
                if callback not in self._subscribers[event_type]:
                    self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> bool:
        """
        Unsubscribe a callback from a specific event type or from wildcard "*".
        Returns True if found and removed, False otherwise.
        """
        with self._lock:
            if event_type == "*":
                if callback in self._wildcard_subscribers:
                    self._wildcard_subscribers.remove(callback)
                    return True
            else:
                if event_type in self._subscribers and callback in self._subscribers[event_type]:
                    self._subscribers[event_type].remove(callback)
                    return True
            return False

    def publish(self, event: Event) -> int:
        """
        Publish an event. Subscribers are triggered synchronously.
        Order of delivery:
        1. Specific event_type subscribers, in registration order.
        2. Wildcard "*" subscribers, in registration order.
        Returns the number of successful deliveries.
        """
        if self._metrics:
            self._metrics.record_publish(event)

        # Retrieve a snapshot of the subscribers to execute outside lock
        with self._lock:
            specific_subs = list(self._subscribers.get(event.event_type, []))
            wildcard_subs = list(self._wildcard_subscribers)

        targets = specific_subs + wildcard_subs
        delivered = 0

        for callback in targets:
            try:
                callback(event)
                delivered += 1
            except Exception as e:
                logger.error(
                    f"Error in subscriber {getattr(callback, '__name__', str(callback))} "
                    f"handling event {event.event_id} ({event.event_type}): {e}",
                    exc_info=True
                )
                if self._metrics:
                    self._metrics.record_delivery_failure()

        return delivered
