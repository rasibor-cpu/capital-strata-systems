"""
CSS Enterprise Event Bus Package (EIP-1 Scaffolding)

This package exposes the key entities for registering, publishing,
subscribing to, filtering, and replaying events.
It also provides default singleton instances for convenience.
"""

from backend.events.event_models import Event
from backend.events.event_registry import *
from backend.events.event_metrics import EventMetrics
from backend.events.event_bus import EventBus
from backend.events.event_store import EventStore
from backend.events.event_filters import EventFilter
from backend.events.event_replay import EventReplay

# Instantiate default singletons for CSS-wide usage
_default_metrics = EventMetrics()
_default_store = EventStore(metrics=_default_metrics)
_default_bus = EventBus(metrics=_default_metrics)
_default_replay = EventReplay(_default_store)

# Auto-subscribe default store to receive and write all published events to JSONL
_default_bus.subscribe("*", _default_store.append)

def get_default_bus() -> EventBus:
    """Get the default EventBus singleton."""
    return _default_bus

def get_default_store() -> EventStore:
    """Get the default EventStore singleton."""
    return _default_store

def get_default_metrics() -> EventMetrics:
    """Get the default EventMetrics singleton."""
    return _default_metrics

def get_default_replay() -> EventReplay:
    """Get the default EventReplay singleton."""
    return _default_replay

# Convenience package-level APIs targeting the default singleton instances
def publish(event: Event) -> int:
    """Publish an event to the default EventBus (will be auto-persisted to store)."""
    return _default_bus.publish(event)

def subscribe(event_type: str, callback) -> None:
    """Subscribe a callback to the default EventBus."""
    _default_bus.subscribe(event_type, callback)

def unsubscribe(event_type: str, callback) -> bool:
    """Unsubscribe a callback from the default EventBus."""
    return _default_bus.unsubscribe(event_type, callback)
