"""
Tests for Enterprise Event Subscribers and Visibility Layer (EWP-2B/2C)
"""

import pytest
import os
import tempfile
import time
from backend.events.event_bus import EventBus
from backend.events.event_models import Event
from backend.events.event_subscription_manager import EventSubscriptionManager
from backend.events.visibility_layer import EventVisibilityLayer

from backend.notifications.notification_service import NotificationService, NotificationConfig
from backend.notifications.notification_queue import NotificationQueue
from backend.notifications.notification_history import NotificationHistory
from backend.notifications.notification_delivery import NotificationDeliveryRouter
from backend.notifications.notification_templates import NotificationTemplates
from backend.notifications.notification_scheduler import NotificationScheduler

from backend.reporting.reporting_service import ReportingService, ReportingConfig
from backend.reporting.report_generator import ReportGenerator
from backend.reporting.report_archive import ReportArchive
from backend.reporting.report_history import ReportHistory
from backend.reporting.report_scheduler import ReportScheduler
from backend.reporting.report_templates import ReportTemplates

from backend.operations.operations_service import OperationsService, OperationsConfig
from backend.operations.health_monitor import HealthMonitor
from backend.operations.operational_state_manager import OperationalStateManager
from backend.operations.operational_timeline import OperationalTimeline
from backend.operations.runtime_statistics import RuntimeStatistics


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def services(temp_dir):
    # Notification setup
    q_file = os.path.join(temp_dir, "queue.json")
    h_file = os.path.join(temp_dir, "history.json")
    n_config = NotificationConfig()
    n_queue = NotificationQueue(file_path=q_file)
    n_history = NotificationHistory(file_path=h_file)
    n_router = NotificationDeliveryRouter()
    n_templates = NotificationTemplates()
    n_scheduler = NotificationScheduler()
    notification_service = NotificationService(
        config=n_config,
        queue=n_queue,
        history=n_history,
        router=n_router,
        templates=n_templates,
        scheduler=n_scheduler
    )

    # Reporting setup
    arch_dir = os.path.join(temp_dir, "reports")
    rep_hist_file = os.path.join(temp_dir, "report_history.json")
    r_config = ReportingConfig(archive_dir=arch_dir, history_file=rep_hist_file)
    r_generator = ReportGenerator(templates=ReportTemplates())
    r_archive = ReportArchive(archive_dir=arch_dir)
    r_history = ReportHistory(history_file=rep_hist_file)
    r_scheduler = ReportScheduler()
    reporting_service = ReportingService(
        config=r_config,
        generator=r_generator,
        archive=r_archive,
        history=r_history,
        scheduler=r_scheduler
    )

    # Operations setup
    state_file = os.path.join(temp_dir, "ops_state.json")
    timeline_file = os.path.join(temp_dir, "ops_timeline.json")
    o_config = OperationsConfig(state_file=state_file, timeline_file=timeline_file)
    o_monitor = HealthMonitor()
    o_state_manager = OperationalStateManager(file_path=state_file)
    o_timeline = OperationalTimeline(file_path=timeline_file)
    o_statistics = RuntimeStatistics()
    operations_service = OperationsService(
        config=o_config,
        monitor=o_monitor,
        state_manager=o_state_manager,
        timeline=o_timeline,
        statistics=o_statistics
    )

    return {
        "notification": notification_service,
        "reporting": reporting_service,
        "operations": operations_service,
        "paths": {
            "queue": q_file,
            "history": h_file,
            "report_history": rep_hist_file,
            "state": state_file,
            "timeline": timeline_file
        }
    }


def test_subscription_manager_wiring(services):
    bus = EventBus()
    manager = EventSubscriptionManager(bus)

    # Register dummy desktop channel provider
    from backend.notifications.providers.provider_base import BaseNotificationProvider
    class MockProvider(BaseNotificationProvider):
        @property
        def channel_name(self) -> str:
            return "desktop"
        def send(self, event: Event) -> bool:
            return True

    services["notification"].router.register_provider(MockProvider())

    # Wire services
    manager.wire_notification_service(services["notification"])
    manager.wire_reporting_service(services["reporting"])
    manager.wire_operations_service(services["operations"])

    # Verify that subscribers are registered
    # Let's publish a RUNTIME_STARTED event
    event = Event(
        event_type="RUNTIME_STARTED",
        severity="INFO",
        category="SYSTEM",
        source="test_source",
        payload={"started_by": "unit_test"}
    )
    bus.publish(event)

    # Alert event that qualifies for Notification
    alert_event = Event(
        event_type="TRADE_REJECTED",
        severity="WARNING",
        category="TRADING",
        source="test_source",
        payload={"reason": "risk_limit", "delivery_channels": ["desktop"]}
    )
    bus.publish(alert_event)

    # Notification Service should have received and history logged it
    assert len(services["notification"].history.load()) == 1

    # Reporting Service wildcard subscriber should have ingested both events
    import json
    ingested_file = "artifacts/reports/ingested_events.json"
    assert os.path.exists(ingested_file)
    with open(ingested_file, "r") as f:
        ingested = json.load(f)
    assert len(ingested) >= 2

    # Operations Service should have recorded the events to the timeline
    assert len(services["operations"].timeline.load()) == 2
    assert services["operations"].statistics.get_summary()["counters"]["messages"] == 2

    # Clean up ingested file after test
    if os.path.exists(ingested_file):
        os.remove(ingested_file)


def test_visibility_read_model(services, temp_dir):
    # Setup some dummy data in temp paths
    ev_store_file = os.path.join(temp_dir, "events_store.jsonl")
    
    from backend.common.persistence import append_jsonl, save_json
    import threading
    lock = threading.Lock()
    
    event1 = Event("TRADE_APPROVED", "INFO", "TRADING", "test", {"id": 1})
    event2 = Event("TRADE_REJECTED", "WARNING", "TRADING", "test", {"id": 2})
    
    append_jsonl(ev_store_file, event1.to_dict(), lock)
    append_jsonl(ev_store_file, event2.to_dict(), lock)

    # Populate notification history and queue
    save_json(services["paths"]["queue"], [event1.to_dict()], lock)
    save_json(services["paths"]["history"], [event1.to_dict(), event2.to_dict()], lock)

    # Populate operations state and timeline
    state_event = Event("SYSTEM_STATE_SNAPSHOT", "INFO", "SYSTEM", "ops", {
        "overall_status": "HEALTHY",
        "health_score": 95.5,
        "component_states": {"db": "OK"}
    })
    save_json(services["paths"]["state"], state_event.to_dict(), lock)
    save_json(services["paths"]["timeline"], [event1.to_dict(), event2.to_dict()], lock)

    # Read from Visibility Layer
    visibility = EventVisibilityLayer(
        event_store_file=ev_store_file,
        notification_queue_file=services["paths"]["queue"],
        notification_history_file=services["paths"]["history"],
        operational_state_file=services["paths"]["state"],
        operational_timeline_file=services["paths"]["timeline"]
    )

    # 1. get_recent_events
    events = visibility.get_recent_events(limit=5)
    assert len(events) == 2
    assert events[0].event_type == "TRADE_APPROVED"

    # 2. get_notification_summary
    n_summary = visibility.get_notification_summary()
    assert n_summary["queue_count"] == 1
    assert n_summary["total_history_count"] == 2

    # 3. get_operations_summary
    o_summary = visibility.get_operations_summary()
    assert o_summary["overall_status"] == "HEALTHY"
    assert o_summary["health_score"] == 95.5
    assert o_summary["timeline_length"] == 2


def test_subscriber_isolation():
    bus = EventBus()
    
    # Register normal subscriber
    normal_called = []
    bus.subscribe("TEST_EVENT", lambda e: normal_called.append(e))

    # Register failing subscriber
    def failing_cb(e):
        raise ValueError("Subscriber failed")
    bus.subscribe("TEST_EVENT", failing_cb)

    # Publish event
    event = Event("TEST_EVENT", "INFO", "SYSTEM", "test", {})
    delivered = bus.publish(event)

    assert len(normal_called) == 1
    assert delivered == 1
