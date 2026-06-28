"""
Tests for Component C: Operations Control Centre Foundation
"""

import os
import pytest
from backend.events.event_models import Event
from backend.operations import (
    create_health_check_event,
    HealthMonitor,
    OperationalStateManager,
    OperationalTimeline,
    RuntimeStatistics,
    OperationsConfig,
    OperationsService,
)

def test_health_check_event_creation():
    event = create_health_check_event(
        component="broker_api",
        status="WARN",
        message="Latency high",
        latency_ms=450.5,
        details={"ping": 450.5}
    )
    assert event.event_type == "HEALTH_CHECK_RESULT"
    assert event.severity == "WARNING"
    assert event.payload["component"] == "broker_api"
    assert event.payload["status"] == "WARN"
    assert event.payload["latency_ms"] == 450.5


def test_monitor_scoring():
    monitor = HealthMonitor()
    
    event_ok = create_health_check_event("c1", "OK", "Fine", 10.0)
    event_warn = create_health_check_event("c2", "WARN", "Degraded", 50.0)
    event_crit = create_health_check_event("c3", "CRITICAL", "Dead", 500.0)

    score_all_ok = monitor.calculate_health_score([event_ok, event_ok])
    assert score_all_ok == 100.0

    score_mixed = monitor.calculate_health_score([event_ok, event_warn])
    assert score_mixed == 75.0

    score_with_crit = monitor.calculate_health_score([event_ok, event_crit])
    assert score_with_crit == 50.0


def test_state_manager_and_timeline(tmp_path):
    state_file = tmp_path / "state.json"
    timeline_file = tmp_path / "timeline.json"

    state_mgr = OperationalStateManager(file_path=str(state_file))
    timeline = OperationalTimeline(file_path=str(timeline_file))

    monitor = HealthMonitor()
    statistics = RuntimeStatistics()

    config = OperationsConfig(default_source="ops_control")
    service = OperationsService(
        config=config,
        monitor=monitor,
        state_manager=state_mgr,
        timeline=timeline,
        statistics=statistics
    )

    monitor.register_checker("database", lambda: create_health_check_event("database", "OK", "Connected", 5.0))
    monitor.register_checker("risk_gate", lambda: create_health_check_event("risk_gate", "OK", "Active", 1.0))

    state_event = service.run_diagnostics()
    assert state_event.payload["overall_status"] == "HEALTHY"
    assert state_event.payload["health_score"] == 100.0
    assert len(state_mgr.load()) == 1
    assert state_mgr.load()[0].event_id == state_event.event_id
    assert len(timeline.load()) == 0

    # Modify checker to simulate status change
    monitor.register_checker("risk_gate", lambda: create_health_check_event("risk_gate", "WARN", "Warning limits", 2.0))

    state_event2 = service.run_diagnostics()
    assert state_event2.payload["overall_status"] == "DEGRADED"
    assert state_event2.payload["health_score"] == 75.0

    timeline_events = timeline.load()
    assert len(timeline_events) == 1
    assert timeline_events[0].event_type == "TIMELINE_EVENT"
    assert "transitioned from HEALTHY to DEGRADED" in timeline_events[0].payload["message"]


def test_runtime_statistics():
    stats = RuntimeStatistics()
    stats.increment("messages_processed", 5)
    stats.increment("messages_processed")
    stats.set_gauge("cpu_percent", 14.5)

    summary = stats.get_summary()
    assert summary["counters"]["messages_processed"] == 6
    assert summary["gauges"]["cpu_percent"] == 14.5

    stats.reset()
    assert len(stats.get_summary()["counters"]) == 0
