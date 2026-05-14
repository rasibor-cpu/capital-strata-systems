from __future__ import annotations

import json

from dashboard.runtime.api_bridge import (
    create_app,
    get_runtime_event_persistence_report_payload,
)
from dashboard.runtime.runtime_event_bus import RuntimeEventBus, build_runtime_event
from dashboard.runtime.runtime_event_persistence_policy import (
    RuntimeEventPersistencePolicy,
)
from dashboard.runtime.runtime_event_persistence_report import (
    RUNTIME_EVENT_PERSISTENCE_REPORT_VERSION,
    build_runtime_event_persistence_report,
)
from dashboard.runtime.runtime_event_persistence_scenario import (
    build_runtime_event_persistence_scenario_report,
)
from dashboard.runtime.runtime_event_persistence_simulator import (
    simulate_runtime_event_persistence,
)


def _event() -> dict[str, object]:
    return build_runtime_event(
        {"event_type": "alert_created", "api_token": "hide-me"},
        subsystem="alerting",
        severity="INFO",
        correlation_id="COR-REPORT",
        source_module="tests.dashboard.test_runtime_event_persistence_report",
        timestamp_utc="2026-05-13T22:00:00+00:00",
    )


def test_report_generation_is_json_safe_and_non_persistent() -> None:
    simulation = simulate_runtime_event_persistence([_event()])
    scenario = build_runtime_event_persistence_scenario_report(simulation)
    report = build_runtime_event_persistence_report(
        simulation,
        scenario,
        generated_at_utc="2026-05-13T22:30:00+00:00",
    )
    serialized = json.dumps(report, sort_keys=True)

    assert report["payload_version"] == RUNTIME_EVENT_PERSISTENCE_REPORT_VERSION
    assert report["report_id"].startswith("EVREPORT-")
    assert report["generated_at_utc"] == "2026-05-13T22:30:00+00:00"
    assert report["simulation_only"] is True
    assert report["persistence_enabled"] is False
    assert report["writes_performed"] is False
    assert report["read_only"] is True
    assert report["export_format"] == "json"
    assert "hide-me" not in serialized
    assert "NO_RUNTIME_EVENT_WRITES" in report["safety_assertions"]


def test_report_includes_policy_summary_scenario_and_blockers() -> None:
    simulation = simulate_runtime_event_persistence([_event()])
    report = build_runtime_event_persistence_report(simulation)

    assert report["retention_policy_summary"]["redaction_required"] is True
    assert (
        report["persistence_approval_policy_summary"]["persistence_enabled"]
        is False
    )
    assert (
        report["persistence_approval_policy_summary"]["approval_token_required"]
        is True
    )
    assert report["simulator_summary"]["rejected_events_count"] >= 1
    assert report["backend_scenario_comparison"]
    assert report["recommended_backend"] == "jsonl_append_only"
    assert "PERSISTENCE_DISABLED_BY_POLICY" in report["governance_blockers"]
    assert "explicit operator approval" in report["remaining_approval_requirements"]
    assert report["pcnrass_readiness_notes"]


def test_report_can_describe_accepted_dry_run_without_activating_persistence() -> None:
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
    report = build_runtime_event_persistence_report(simulation)

    assert report["simulator_summary"]["accepted_events_count"] == 1
    assert report["simulator_summary"]["persistence_enabled"] is False
    assert report["persistence_enabled"] is False
    assert report["writes_performed"] is False
    assert "PCNRASS release check" in report["remaining_approval_requirements"]


def test_report_api_route_is_read_only_and_does_not_mutate_bus() -> None:
    bus = RuntimeEventBus()
    bus.publish(_event())
    app = create_app(runtime_event_bus=bus)
    routes = {getattr(route, "path", "") for route in app.routes}
    report = get_runtime_event_persistence_report_payload(bus, limit=10)

    assert "/api/v1/runtime-event-persistence-report" in routes
    assert report["simulation_only"] is True
    assert report["persistence_enabled"] is False
    assert report["writes_performed"] is False
    assert report["recommended_backend"]
    assert len(bus.get_recent(10)) == 1
