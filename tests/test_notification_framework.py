"""
Tests for Component A: Enterprise Notification Framework
"""

import os
import time
import pytest
from backend.events.event_models import Event
from backend.notifications import (
    create_notification_event,
    UserPreferences,
    NotificationQueue,
    NotificationHistory,
    NotificationDeliveryRouter,
    NotificationTemplates,
    NotificationScheduler,
    NotificationConfig,
    NotificationService,
)
from backend.notifications.providers.email_provider import EmailNotificationProvider
from backend.notifications.providers.sms_provider import SMSNotificationProvider


def test_notification_event_creation():
    event = create_notification_event(
        severity="INFO",
        category="ORDER",
        title="Order Filled",
        message="Your buy order was executed.",
        user_id="user1",
        delivery_channels=["email", "sms"],
        payload={"extra": 123}
    )
    assert event.event_type == "NOTIFICATION_DISPATCH"
    assert event.severity == "INFO"
    assert event.user_id == "user1"
    assert event.payload["title"] == "Order Filled"
    assert event.payload["delivery_channels"] == ["email", "sms"]
    assert event.payload["custom_payload"] == {"extra": 123}


def test_notification_queue_and_history_persistence(tmp_path):
    queue_file = tmp_path / "queue.json"
    history_file = tmp_path / "history.json"

    queue = NotificationQueue(file_path=str(queue_file))
    history = NotificationHistory(file_path=str(history_file))

    event = create_notification_event(
        severity="INFO",
        category="ORDER",
        title="Test Alert",
        message="A test message",
        user_id="user1",
        delivery_channels=["email"]
    )

    # Queue checks
    queue.append(event)
    assert os.path.exists(queue_file)
    events_in_queue = queue.load()
    assert len(events_in_queue) == 1
    assert events_in_queue[0].event_id == event.event_id

    dequeued = queue.dequeue()
    assert dequeued.event_id == event.event_id
    assert len(queue.load()) == 0

    # History checks
    history.append(event)
    assert os.path.exists(history_file)
    events_in_history = history.load()
    assert len(events_in_history) == 1
    assert events_in_history[0].event_id == event.event_id

    history.clear()
    assert len(history.load()) == 0


def test_preferences_filtering():
    prefs = UserPreferences(
        user_id="user1",
        enabled_channels=["email"],
        severity_threshold="WARNING",
        quiet_hours_start="22:00",
        quiet_hours_end="08:00"
    )

    # Check channel
    assert prefs.is_channel_enabled("email") is True
    assert prefs.is_channel_enabled("sms") is False

    # Check severity threshold (using timestamp outside quiet hours)
    ts_active = 1782744000
    assert prefs.should_deliver("DEBUG", ts_active) is False
    assert prefs.should_deliver("INFO", ts_active) is False
    assert prefs.should_deliver("WARNING", ts_active) is True
    assert prefs.should_deliver("CRITICAL", ts_active) is True

    # Quiet hours checking (Wed Jun 17 23:00:00 2026 UTC vs Wed Jun 17 12:00:00 2026 UTC)
    ts_quiet = 1782783600

    assert prefs.should_deliver("WARNING", ts_quiet) is False
    assert prefs.should_deliver("WARNING", ts_active) is True


def test_service_delivery_and_retry(tmp_path):
    queue_file = tmp_path / "queue.json"
    history_file = tmp_path / "history.json"

    config = NotificationConfig(max_retries=2)
    queue = NotificationQueue(file_path=str(queue_file))
    history = NotificationHistory(file_path=str(history_file))
    router = NotificationDeliveryRouter()
    templates = NotificationTemplates()
    scheduler = NotificationScheduler()

    service = NotificationService(
        config=config,
        queue=queue,
        history=history,
        router=router,
        templates=templates,
        scheduler=scheduler
    )

    # Register providers
    email_prov = EmailNotificationProvider()
    sms_prov = SMSNotificationProvider()
    router.register_provider(email_prov)
    router.register_provider(sms_prov)

    # Set user prefs
    service.set_user_preferences("user1", UserPreferences(user_id="user1", enabled_channels=["email"]))

    event = create_notification_event(
        severity="INFO",
        category="ORDER",
        title="Immediate Deliver",
        message="Ready",
        user_id="user1",
        delivery_channels=["email", "sms"]
    )

    # Notify immediately
    delivered = service.notify(event)
    assert delivered is True
    assert event.payload["delivery_status"] == "SENT"
    assert len(history.load()) == 1

    # Test failure retry path by unregistering provider
    router.unregister_provider("email")
    event2 = create_notification_event(
        severity="INFO",
        category="ORDER",
        title="Fail Deliver",
        message="Fail",
        user_id="user1",
        delivery_channels=["email"]
    )

    success = service.notify(event2)
    assert success is False
    assert event2.payload["delivery_status"] == "RETRYING"
    assert len(queue.load()) == 1

    # Process queue (retry 1)
    processed = service.process_queue()
    assert processed == 1
    queued_events = queue.load()
    assert len(queued_events) == 1
    assert queued_events[0].payload["retry_count"] == 1

    # Process queue (retry 2 -> max retry reached)
    processed = service.process_queue()
    assert processed == 1
    assert len(queue.load()) == 0
    hist_events = history.load()
    # History contains SENT and FAILED events
    assert len(hist_events) == 2
    assert hist_events[0].payload["delivery_status"] == "SENT"
    assert hist_events[1].payload["delivery_status"] == "FAILED"


def test_scheduler_operation():
    scheduler = NotificationScheduler()
    event1 = create_notification_event(
        severity="INFO", category="ORDER", title="A", message="A", user_id="u", delivery_channels=[]
    )
    event2 = create_notification_event(
        severity="INFO", category="ORDER", title="B", message="B", user_id="u", delivery_channels=[]
    )

    now = time.time()
    scheduler.schedule(event1, now - 10)  # Due
    scheduler.schedule(event2, now + 10)  # Future

    pending = scheduler.get_pending(now)
    assert len(pending) == 1
    assert pending[0].event_id == event1.event_id
    assert len(scheduler._schedule) == 1
