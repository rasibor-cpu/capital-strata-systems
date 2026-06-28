"""
Event Filters for CSS Enterprise Event Bus

Provides composable, pure-function filter predicates for query, replay, or dispatch routing.
"""

from typing import Callable, Optional
from backend.events.event_models import Event

def by_type(event_type: str) -> Callable[[Event], bool]:
    """Filter events that match the exact event_type."""
    return lambda e: e.event_type == event_type

def by_category(category: str) -> Callable[[Event], bool]:
    """Filter events that match the exact category."""
    return lambda e: e.category == category

def by_severity(severity: str) -> Callable[[Event], bool]:
    """Filter events that match the exact severity."""
    return lambda e: e.severity == severity

def by_correlation_id(correlation_id: str) -> Callable[[Event], bool]:
    """Filter events that match the exact correlation_id."""
    return lambda e: e.correlation_id == correlation_id

def by_time_range(start_time: Optional[float] = None, end_time: Optional[float] = None) -> Callable[[Event], bool]:
    """Filter events that fall within the given epoch time range [start_time, end_time]."""
    def filter_func(e: Event) -> bool:
        if start_time is not None and e.timestamp < start_time:
            return False
        if end_time is not None and e.timestamp > end_time:
            return False
        return True
    return filter_func

class EventFilter:
    """Combines multiple filters using logical AND execution."""
    def __init__(self, *filters: Callable[[Event], bool]):
        self.filters = list(filters)

    def match(self, event: Event) -> bool:
        """Returns True if the event matches all defined criteria, False otherwise."""
        return all(f(event) for f in self.filters)
