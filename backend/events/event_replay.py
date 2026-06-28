"""
Event Replay for CSS Enterprise Event Bus

Enables historical query, filtering, and re-emission of persisted events.
Supports filtering by event type, category, or correlation ID.
"""

from typing import List, Optional
from backend.events.event_models import Event
from backend.events.event_store import EventStore

class EventReplay:
    def __init__(self, store: EventStore):
        self.store = store

    def replay(
        self,
        event_type: Optional[str] = None,
        category: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> List[Event]:
        """
        Replay events from store matching specified criteria.
        If no criteria are provided, all events are returned.
        """
        matched = []
        for event in self.store.read_all():
            if event_type is not None and event.event_type != event_type:
                continue
            if category is not None and event.category != category:
                continue
            if correlation_id is not None and event.correlation_id != correlation_id:
                continue
            matched.append(event)
        return matched
