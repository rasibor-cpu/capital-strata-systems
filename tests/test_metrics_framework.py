"""
Tests for Enterprise Metrics & Telemetry Subsystem (EWP-2D)
"""

import pytest
import os
import tempfile
import time
from backend.events.event_models import Event
from backend.events.event_bus import EventBus
from backend.events.event_subscription_manager import EventSubscriptionManager
from backend.metrics.metrics_snapshot import MetricsSnapshot
from backend.metrics.metrics_registry import MetricsRegistry
from backend.metrics.telemetry import TelemetryCollector
from backend.metrics.health_metrics import HealthEvaluator
from backend.metrics.metrics_history import MetricsHistory
from backend.metrics.metrics_service import MetricsService


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield td


def test_metrics_registry():
    registry = MetricsRegistry()
    
    registry.increment("trades_approved", 3)
    registry.increment("trades_rejected", 1)
    
    counters = registry.get_all()
    assert counters["trades_approved"] == 3
    assert counters["trades_rejected"] == 1
    assert counters["events_published"] == 0


def test_telemetry_collector():
    collector = TelemetryCollector()
    
    collector.record_latency(10.0)
    collector.record_latency(20.0)
    collector.record_queues(notif_depth=5, report_backlog=2)
    collector.record_heartbeat()
    
    telemetry = collector.compile_telemetry(event_count=50)
    assert telemetry["publish_latency_avg_ms"] == 15.0
    assert telemetry["notification_queue_depth"] == 5
    assert telemetry["reporting_backlog"] == 2
    assert telemetry["heartbeat_age_seconds"] >= 0
    assert telemetry["runtime_uptime_seconds"] >= 0


def test_health_evaluator():
    # Test perfect health
    h1 = HealthEvaluator.calculate_health(
        restart_count=0,
        heartbeat_age=10.0,
        notif_delivered=10,
        notif_failed=0,
        report_backlog=0,
        subscriber_failures=0
    )
    assert h1["overall_health_score"] == 100.0
    assert h1["runtime_health"] == 100.0
    assert h1["notification_health"] == 100.0

    # Test degraded health (one restart, failures, backlog)
    h2 = HealthEvaluator.calculate_health(
        restart_count=1,          # -15
        heartbeat_age=10.0,
        notif_delivered=9,
        notif_failed=1,           # 10% fail -> -10
        report_backlog=4,         # -20
        subscriber_failures=2     # -20
    )
    assert h2["runtime_health"] == 85.0
    assert h2["notification_health"] == 90.0
    assert h2["reporting_health"] == 80.0
    assert h2["operations_health"] == 80.0
    assert h2["overall_health_score"] == 83.75


def test_snapshot_serialization():
    snapshot = MetricsSnapshot(
        timestamp=123456.78,
        metrics={"trades_approved": 5},
        telemetry={"event_throughput_per_sec": 1.2},
        health={"overall_health_score": 90.0}
    )
    
    serialized = snapshot.to_dict()
    assert serialized["timestamp"] == 123456.78
    assert serialized["metrics"]["trades_approved"] == 5
    
    deserialized = MetricsSnapshot.from_dict(serialized)
    assert deserialized.timestamp == 123456.78
    assert deserialized.metrics["trades_approved"] == 5


def test_metrics_history_persistence(temp_dir):
    hist_file = os.path.join(temp_dir, "metrics_snapshots.json")
    history = MetricsHistory(file_path=hist_file)
    
    snapshot1 = MetricsSnapshot(metrics={"events_published": 10})
    snapshot2 = MetricsSnapshot(metrics={"events_published": 20})
    
    history.append(snapshot1)
    history.append(snapshot2)
    
    loaded = history.load()
    assert len(loaded) == 2
    assert loaded[0].metrics["events_published"] == 10
    assert loaded[1].metrics["events_published"] == 20


def test_metrics_service_wiring_and_isolation(temp_dir):
    bus = EventBus()
    manager = EventSubscriptionManager(bus)
    
    hist_file = os.path.join(temp_dir, "metrics_snapshots.json")
    registry = MetricsRegistry()
    telemetry = TelemetryCollector()
    history = MetricsHistory(file_path=hist_file)
    
    service = MetricsService(registry=registry, telemetry=telemetry, history=history)
    
    # Wire the metrics service
    manager.wire_metrics_service(service)
    
    # Publish events to event bus
    e1 = Event("TRADE_APPROVED", "INFO", "TRADING", "test", {})
    e2 = Event("RUNTIME_STARTED", "INFO", "SYSTEM", "test", {})
    e3 = Event("NOTIFICATION_DISPATCH", "WARNING", "SYSTEM", "test", {"delivery_status": "SENT"})
    
    bus.publish(e1)
    bus.publish(e2)
    bus.publish(e3)
    
    # Verify counter aggregates in registry
    counters = service.get_current_metrics()
    assert counters["events_published"] == 3
    assert counters["trades_approved"] == 1
    assert counters["runtime_starts"] == 1
    assert counters["notifications_delivered"] == 1
    
    # Persist and query
    service.persist_snapshot()
    historical = service.get_recent_snapshots()
    assert len(historical) == 1
    
    latest = service.get_latest_snapshot()
    assert latest.metrics["events_published"] == 3
    assert latest.health["overall_health_score"] == 100.0
    
    # Unwire and verify events are not received
    manager.unwire_metrics_service(service)
    bus.publish(e1)
    
    counters_after = service.get_current_metrics()
    assert counters_after["events_published"] == 3  # Did not increase
