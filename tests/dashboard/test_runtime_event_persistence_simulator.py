from __future__ import annotations

import json

from dashboard.runtime.api_bridge import (
    create_app,
    get_runtime_event_persistence_sim_payload,
)
from dashboard.runtime.runtime_event_bus import RuntimeEventBus, build_runtime_event
from dashboard.runtime.runtime_event_inspector import RuntimeEventRetentionPolicy
from dashboard.runtime.runtime_event_persistence_policy import (
    RuntimeEventPersistencePolicy,
)
from dashboard.runtime.runtime_event_persistence_simulator import (
    RUNTIME_EVENT_PERSISTENCE_SIMULATOR_VERSION,
    get_runtime_event_persistence_simulation_payload,
    simulate_runtime_event_persistence,
)


def _event(
    event_type: str = "alert_created",
    subsystem: str = "alerting",
    correlation_id: str = "COR-SIM",
) -> dict[str, object]:
    return build_runtime_event(
        {"event_type": event_type, "message": "simulation event"},
        subsystem=subsystem,
        severity="INFO",
        correlation_id=correlation_id,
        source_module="tests.dashboard.test_runtime_event_persistence_simulator",
        timestamp_utc="2026-05-13T20:00:00+00:00",
    )


def test_empty_simulation_is_safe_and_non_persistent() -> None:
    payload = simulate_runtime_event_persistence([])

    assert payload["payload_version"] == RUNTIME_EVENT_PERSISTENCE_SIMULATOR_VERSION
    assert payload["simulation_only"] is True
    assert payload["read_only"] is True
    assert payload["writes_performed"] is False
    assert payload["persistence_enabled"] is False
    assert payload["accepted_events_count"] == 0
    assert payload["rejected_events_count"] == 0
    assert payload["estimated_storage_bytes"] == 0


def test_default_disabled_policy_rejects_events_without_writing() -> None:
    payload = simulate_runtime_event_persistence(
        [_event()],
        operator_id="operator-1",
        approval_token_present=True,
        requested_window_minutes=15,
    )

    assert payload["accepted_events_count"] == 0
    assert payload["rejected_events_count"] == 1
    assert payload["rejection_reasons"]["PERSISTENCE_DISABLED_BY_POLICY"] == 1
    assert payload["writes_performed"] is False
    assert payload["persistence_enabled"] is False


def test_enabled_custom_policy_can_simulate_acceptance_without_persistence() -> None:
    policy = RuntimeEventPersistencePolicy(
        persistence_enabled=True,
        approved_subsystems=("alerting",),
        max_persistence_window_minutes=30,
    )
    payload = simulate_runtime_event_persistence(
        [_event()],
        persistence_policy=policy,
        operator_id="operator-1",
        approval_token_present=True,
        requested_window_minutes=15,
    )

    assert payload["accepted_events_count"] == 1
    assert payload["rejected_events_count"] == 0
    assert payload["estimated_storage_bytes"] > 0
    assert payload["estimated_event_rate"] > 0
    assert payload["subsystem_breakdown"]["alerting"]["accepted"] == 1
    assert payload["persistence_enabled"] is False
    assert payload["writes_performed"] is False


def test_rejected_subsystem_is_reported() -> None:
    policy = RuntimeEventPersistencePolicy(
        persistence_enabled=True,
        approved_subsystems=("alerting",),
    )
    payload = simulate_runtime_event_persistence(
        [_event(subsystem="unsupported_subsystem")],
        persistence_policy=policy,
        operator_id="operator-1",
        approval_token_present=True,
    )

    assert payload["accepted_events_count"] == 0
    assert payload["rejected_events_count"] == 1
    assert (
        payload["rejection_reasons"]["UNAPPROVED_SUBSYSTEM:unsupported_subsystem"]
        == 1
    )


def test_oversized_export_is_capped_and_reported() -> None:
    policy = RuntimeEventPersistencePolicy(
        persistence_enabled=True,
        approved_subsystems=("alerting",),
    )
    retention = RuntimeEventRetentionPolicy(
        max_events=10,
        max_export_limit=2,
        default_inspection_limit=10,
    )
    events = [_event(correlation_id=f"COR-{index}") for index in range(4)]

    payload = simulate_runtime_event_persistence(
        events,
        retention_policy=retention,
        persistence_policy=policy,
        operator_id="operator-1",
        approval_token_present=True,
        limit=10,
    )

    assert payload["evaluated_events_count"] == 2
    assert payload["truncated_events_count"] == 2
    assert payload["accepted_events_count"] == 2
    assert payload["rejected_events_count"] == 2
    assert payload["rejection_reasons"]["EXPORT_LIMIT_EXCEEDED"] == 2


def test_redaction_failures_are_safe_and_do_not_leak_secret_values() -> None:
    raw_event = {
        "schema_version": "css.runtime_event.v1",
        "event_id": "EVT-RAW",
        "correlation_id": "COR-RAW",
        "event_type": "alert_created",
        "subsystem": "alerting",
        "timestamp_utc": "2026-05-13T20:00:00+00:00",
        "severity": "INFO",
        "source_module": "test",
        "redaction_status": "unknown",
        "payload": {"api_token": "super-secret-value"},
    }
    policy = RuntimeEventPersistencePolicy(
        persistence_enabled=True,
        approved_subsystems=("alerting",),
    )
    payload = simulate_runtime_event_persistence(
        [raw_event],
        persistence_policy=policy,
        operator_id="operator-1",
        approval_token_present=True,
    )
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["accepted_events_count"] == 0
    assert payload["rejected_events_count"] == 1
    assert payload["rejection_reasons"]["REDACTION_REQUIRED"] == 1
    assert payload["redaction_failures"][0]["paths"] == ["payload.api_token"]
    assert "super-secret-value" not in serialized


def test_simulation_payload_reads_runtime_bus_without_mutation() -> None:
    bus = RuntimeEventBus()
    bus.publish(_event(subsystem="alerting", correlation_id="COR-A"))
    bus.publish(_event(subsystem="risk", correlation_id="COR-B"))

    payload = get_runtime_event_persistence_simulation_payload(
        bus,
        subsystem="alerting",
        correlation_id="COR-A",
        operator_id="operator-1",
        approval_token_present=True,
    )

    assert payload["bus_available"] is True
    assert payload["source"] == "runtime_event_bus"
    assert payload["filters"]["subsystem"] == "alerting"
    assert payload["inspected_events_count"] == 1
    assert len(bus.get_recent(10)) == 2


def test_api_route_exists_and_helper_is_simulation_only() -> None:
    bus = RuntimeEventBus()
    bus.publish(_event())
    app = create_app(runtime_event_bus=bus)
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_runtime_event_persistence_sim_payload(bus, limit=5)

    assert "/api/v1/runtime-event-persistence-sim" in routes
    assert payload["simulation_only"] is True
    assert payload["writes_performed"] is False
    assert payload["persistence_enabled"] is False
