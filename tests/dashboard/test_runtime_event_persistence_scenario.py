from __future__ import annotations

import json

from dashboard.runtime.api_bridge import (
    create_app,
    get_runtime_event_persistence_scenarios_payload,
)
from dashboard.runtime.runtime_event_bus import RuntimeEventBus, build_runtime_event
from dashboard.runtime.runtime_event_persistence_policy import (
    RuntimeEventPersistencePolicy,
)
from dashboard.runtime.runtime_event_persistence_scenario import (
    RUNTIME_EVENT_PERSISTENCE_SCENARIO_VERSION,
    build_runtime_event_persistence_scenario_report,
)
from dashboard.runtime.runtime_event_persistence_simulator import (
    simulate_runtime_event_persistence,
)
from dashboard.runtime.runtime_event_storage_profiles import (
    RUNTIME_EVENT_STORAGE_PROFILE_VERSION,
    get_runtime_event_storage_profiles_payload,
)


def _event(subsystem: str = "alerting") -> dict[str, object]:
    return build_runtime_event(
        {"event_type": "alert_created", "api_token": "hide-me"},
        subsystem=subsystem,
        severity="INFO",
        correlation_id="COR-SCENARIO",
        source_module="tests.dashboard.test_runtime_event_persistence_scenario",
        timestamp_utc="2026-05-13T21:00:00+00:00",
    )


def test_storage_backend_profiles_are_simulation_only_and_complete() -> None:
    payload = get_runtime_event_storage_profiles_payload()
    names = {profile["backend_name"] for profile in payload["profiles"]}

    assert payload["payload_version"] == RUNTIME_EVENT_STORAGE_PROFILE_VERSION
    assert payload["read_only"] is True
    assert payload["simulation_only"] is True
    assert payload["persistence_enabled"] is False
    assert payload["writes_performed"] is False
    assert {
        "jsonl_append_only",
        "sqlite_local_indexed",
        "structured_append_log",
        "future_external_queue_stream",
    } <= names
    for profile in payload["profiles"]:
        assert profile["estimated_storage_multiplier"] > 0
        assert profile["recommended_for"]
        assert profile["risks"]
        assert profile["governance_notes"]


def test_scenario_recommends_jsonl_for_first_local_backend_without_writes() -> None:
    policy = RuntimeEventPersistencePolicy(
        persistence_enabled=True,
        approved_subsystems=("alerting",),
    )
    simulation = simulate_runtime_event_persistence(
        [_event()],
        persistence_policy=policy,
        operator_id="operator-1",
        approval_token_present=True,
    )
    report = build_runtime_event_persistence_scenario_report(simulation)

    assert report["payload_version"] == RUNTIME_EVENT_PERSISTENCE_SCENARIO_VERSION
    assert report["recommended_backend"] == "jsonl_append_only"
    assert report["persistence_enabled"] is False
    assert report["writes_performed"] is False
    assert report["simulation_only"] is True
    assert "STORAGE_BACKEND_NOT_APPROVED" in report["governance_blockers"]


def test_scenario_recommends_sqlite_for_high_rate_local_review() -> None:
    simulation = {
        "accepted_events_count": 5000,
        "rejected_events_count": 0,
        "redaction_failures": [],
        "estimated_storage_bytes": 1000000,
        "estimated_event_rate": 75.0,
        "simulation_id": "SIM-HIGH-RATE",
        "writes_performed": False,
    }
    report = build_runtime_event_persistence_scenario_report(simulation)

    assert report["recommended_backend"] == "sqlite_local_indexed"
    recommended = [
        item
        for item in report["backend_comparison"]
        if item["backend_name"] == "sqlite_local_indexed"
    ][0]
    assert recommended["estimated_backend_storage_bytes"] > simulation["estimated_storage_bytes"]
    assert recommended["governance_suitability"] == "STRONG_FOR_HIGH_RATE_LOCAL_REVIEW"


def test_scenario_reports_rejections_and_redaction_blockers_safely() -> None:
    raw_simulation = {
        "accepted_events_count": 0,
        "rejected_events_count": 1,
        "redaction_failures": [{"paths": ["payload.api_token"]}],
        "estimated_storage_bytes": 0,
        "estimated_event_rate": 1.0,
        "simulation_id": "SIM-BLOCKED",
        "writes_performed": False,
    }
    report = build_runtime_event_persistence_scenario_report(raw_simulation)
    serialized = json.dumps(report, sort_keys=True)

    assert "SIMULATION_REJECTIONS_REQUIRE_REVIEW" in report["governance_blockers"]
    assert "REDACTION_FAILURES_REQUIRE_REMEDIATION" in report["governance_blockers"]
    assert "secret" not in serialized.lower()


def test_scenario_api_route_is_read_only_and_non_persistent() -> None:
    bus = RuntimeEventBus()
    bus.publish(_event())
    app = create_app(runtime_event_bus=bus)
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_runtime_event_persistence_scenarios_payload(bus, limit=10)

    assert "/api/v1/runtime-event-persistence-scenarios" in routes
    assert payload["read_only"] is True
    assert payload["simulation_only"] is True
    assert payload["persistence_enabled"] is False
    assert payload["writes_performed"] is False
    assert payload["storage_profiles"]["profiles"]
    assert payload["scenario_report"]["recommended_backend"]
    assert len(bus.get_recent(10)) == 1
