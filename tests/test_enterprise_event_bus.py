"""
Tests for the EIP-1 Enterprise Event Bus Scaffolding
"""

import os
import pytest
from backend.events.event_models import Event
from backend.events.event_registry import (
    ORDER_CREATED,
    ORDER_FILLED,
    CATEGORY_ORDER,
    SEVERITY_INFO,
    SEVERITY_ERROR,
    SYSTEM_STARTUP,
    CATEGORY_SYSTEM,
    RISK_LIMIT_EXCEEDED,
    CATEGORY_RISK,
)
from backend.events.event_bus import EventBus
from backend.events.event_store import EventStore
from backend.events.event_metrics import EventMetrics
from backend.events.event_replay import EventReplay


def test_event_creation_and_serialization():
    payload = {"symbol": "AAPL", "quantity": 100}
    event = Event(
        event_type=ORDER_CREATED,
        severity=SEVERITY_INFO,
        category=CATEGORY_ORDER,
        source="execution_engine",
        payload=payload,
        correlation_id="corr-123",
        session_id="sess-456",
        user_id="user-789",
    )

    assert event.event_type == ORDER_CREATED
    assert event.severity == SEVERITY_INFO
    assert event.category == CATEGORY_ORDER
    assert event.payload == payload
    assert event.correlation_id == "corr-123"
    assert event.schema_version == "1.0.0"

    event_dict = event.to_dict()
    assert event_dict["event_type"] == ORDER_CREATED
    assert event_dict["payload"] == payload

    cloned_event = Event.from_dict(event_dict)
    assert cloned_event.event_id == event.event_id
    assert cloned_event.timestamp == event.timestamp
    assert cloned_event.correlation_id == "corr-123"


def test_event_bus_pub_sub():
    metrics = EventMetrics()
    bus = EventBus(metrics=metrics)
    received_events = []

    def subscriber_callback(event: Event):
        received_events.append(event)

    bus.subscribe(ORDER_CREATED, subscriber_callback)

    event = Event(
        event_type=ORDER_CREATED,
        severity=SEVERITY_INFO,
        category=CATEGORY_ORDER,
        source="test",
        payload={"test": True},
    )

    delivered = bus.publish(event)
    assert delivered == 1
    assert len(received_events) == 1
    assert received_events[0].event_id == event.event_id
    assert metrics.total_published == 1
    assert metrics.total_failed_deliveries == 0


def test_event_bus_unsubscribe():
    bus = EventBus()
    received_events = []

    def callback(event: Event):
        received_events.append(event)

    bus.subscribe(ORDER_CREATED, callback)
    
    # Try unsubscribe
    unsub_status = bus.unsubscribe(ORDER_CREATED, callback)
    assert unsub_status is True

    event = Event(
        event_type=ORDER_CREATED,
        severity=SEVERITY_INFO,
        category=CATEGORY_ORDER,
        source="test",
        payload={},
    )
    
    delivered = bus.publish(event)
    assert delivered == 0
    assert len(received_events) == 0


def test_multiple_subscribers_and_wildcard():
    bus = EventBus()
    specific_received = []
    wildcard_received = []

    def specific_callback(event: Event):
        specific_received.append(event)

    def wildcard_callback(event: Event):
        wildcard_received.append(event)

    bus.subscribe(ORDER_CREATED, specific_callback)
    bus.subscribe("*", wildcard_callback)

    event1 = Event(
        event_type=ORDER_CREATED,
        severity=SEVERITY_INFO,
        category=CATEGORY_ORDER,
        source="test",
        payload={},
    )
    event2 = Event(
        event_type=ORDER_FILLED,
        severity=SEVERITY_INFO,
        category=CATEGORY_ORDER,
        source="test",
        payload={},
    )

    bus.publish(event1)
    bus.publish(event2)

    assert len(specific_received) == 1
    assert specific_received[0].event_id == event1.event_id

    # Wildcard receives all events
    assert len(wildcard_received) == 2
    assert wildcard_received[0].event_id == event1.event_id
    assert wildcard_received[1].event_id == event2.event_id


def test_safe_exception_handling_in_bus():
    metrics = EventMetrics()
    bus = EventBus(metrics=metrics)
    received = []

    def failing_callback(event: Event):
        raise ValueError("Subscriber failed intentionally")

    def success_callback(event: Event):
        received.append(event)

    # Register both. Even if failing_callback is executed first,
    # success_callback should still run successfully.
    bus.subscribe(ORDER_CREATED, failing_callback)
    bus.subscribe(ORDER_CREATED, success_callback)

    event = Event(
        event_type=ORDER_CREATED,
        severity=SEVERITY_INFO,
        category=CATEGORY_ORDER,
        source="test",
        payload={},
    )

    delivered = bus.publish(event)
    # Delivered should count successful deliveries (1)
    assert delivered == 1
    assert len(received) == 1
    assert received[0].event_id == event.event_id
    assert metrics.total_failed_deliveries == 1


def test_persistence_and_replay(tmp_path):
    metrics = EventMetrics()
    test_jsonl = tmp_path / "test_events.jsonl"
    store = EventStore(file_path=str(test_jsonl), metrics=metrics)
    replay_engine = EventReplay(store)

    event1 = Event(
        event_type=ORDER_CREATED,
        severity=SEVERITY_INFO,
        category=CATEGORY_ORDER,
        source="test",
        payload={},
        correlation_id="corr-1",
    )
    event2 = Event(
        event_type=RISK_LIMIT_EXCEEDED,
        severity=SEVERITY_ERROR,
        category=CATEGORY_RISK,
        source="test",
        payload={},
        correlation_id="corr-2",
    )
    event3 = Event(
        event_type=ORDER_CREATED,
        severity=SEVERITY_INFO,
        category=CATEGORY_ORDER,
        source="test",
        payload={},
        correlation_id="corr-2",
    )

    store.append(event1)
    store.append(event2)
    store.append(event3)

    assert os.path.exists(test_jsonl)
    assert metrics.total_persisted == 3

    # Replay all events
    all_events = replay_engine.replay()
    assert len(all_events) == 3

    # Replay by event type
    type_events = replay_engine.replay(event_type=ORDER_CREATED)
    assert len(type_events) == 2
    assert type_events[0].event_id == event1.event_id
    assert type_events[1].event_id == event3.event_id

    # Replay by category
    category_events = replay_engine.replay(category=CATEGORY_RISK)
    assert len(category_events) == 1
    assert category_events[0].event_type == RISK_LIMIT_EXCEEDED

    # Replay by correlation_id
    corr_events = replay_engine.replay(correlation_id="corr-2")
    assert len(corr_events) == 2
    assert set(e.event_id for e in corr_events) == {event2.event_id, event3.event_id}


def test_metrics_aggregation():
    metrics = EventMetrics()
    
    event1 = Event(
        event_type=ORDER_CREATED,
        severity=SEVERITY_INFO,
        category=CATEGORY_ORDER,
        source="test",
        payload={},
    )
    event2 = Event(
        event_type=SYSTEM_STARTUP,
        severity=SEVERITY_INFO,
        category=CATEGORY_SYSTEM,
        source="test",
        payload={},
    )

    metrics.record_publish(event1)
    metrics.record_publish(event2)
    metrics.record_persist(event1)
    metrics.record_delivery_failure()

    summary = metrics.get_summary()
    assert summary["total_published"] == 2
    assert summary["total_persisted"] == 1
    assert summary["total_failed_deliveries"] == 1
    assert summary["events_by_category"][CATEGORY_ORDER] == 1
    assert summary["events_by_category"][CATEGORY_SYSTEM] == 1
    assert summary["events_by_severity"][SEVERITY_INFO] == 2

    metrics.reset()
    assert metrics.get_summary()["total_published"] == 0
