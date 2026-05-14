from __future__ import annotations

import json

from dashboard.runtime.api_bridge import (
    create_app,
    get_runtime_event_persistence_checklist_payload,
)
from dashboard.runtime.runtime_event_bus import RuntimeEventBus, build_runtime_event
from dashboard.runtime.runtime_event_persistence_checklist import (
    READINESS_NOT_READY,
    READINESS_REVIEW_REQUIRED,
    RUNTIME_EVENT_PERSISTENCE_CHECKLIST_VERSION,
    build_runtime_event_persistence_checklist,
)
from dashboard.runtime.runtime_event_persistence_report import (
    build_runtime_event_persistence_report,
)
from dashboard.runtime.runtime_event_persistence_simulator import (
    simulate_runtime_event_persistence,
)


def _event() -> dict[str, object]:
    return build_runtime_event(
        {"event_type": "alert_created", "message": "review"},
        subsystem="alerting",
        severity="INFO",
        correlation_id="COR-CHECKLIST",
        source_module="tests.dashboard.test_runtime_event_persistence_checklist",
        timestamp_utc="2026-05-13T23:00:00+00:00",
    )


def _clean_report() -> dict[str, object]:
    return {
        "report_id": "EVREPORT-CLEAN",
        "generated_at_utc": "2026-05-13T23:10:00+00:00",
        "simulation_only": True,
        "persistence_enabled": False,
        "writes_performed": False,
        "retention_policy_summary": {"redaction_required": True},
        "persistence_approval_policy_summary": {
            "redaction_required": True,
            "approval_token_required": True,
            "operator_approval_required": True,
        },
        "recommended_backend": "jsonl_append_only",
        "governance_blockers": [],
        "safety_assertions": ["NO_BROKER_OR_TRADING_BEHAVIOR_CHANGED"],
        "pcnrass_readiness_notes": ["PCNRASS release check required"],
        "remaining_approval_requirements": ["explicit operator approval"],
    }


def test_checklist_generation_is_review_only_and_non_persistent() -> None:
    simulation = simulate_runtime_event_persistence([_event()])
    report = build_runtime_event_persistence_report(simulation)
    checklist = build_runtime_event_persistence_checklist(
        report,
        generated_at_utc="2026-05-13T23:20:00+00:00",
    )
    serialized = json.dumps(checklist, sort_keys=True)

    assert checklist["payload_version"] == RUNTIME_EVENT_PERSISTENCE_CHECKLIST_VERSION
    assert checklist["checklist_id"].startswith("EVCHECK-")
    assert checklist["generated_at_utc"] == "2026-05-13T23:20:00+00:00"
    assert checklist["report_id"] == report["report_id"]
    assert checklist["operator_review_required"] is True
    assert checklist["persistence_enabled"] is False
    assert checklist["writes_performed"] is False
    assert checklist["simulation_only"] is True
    assert "secret=" not in serialized.lower()


def test_checklist_is_not_ready_when_governance_blockers_exist() -> None:
    simulation = simulate_runtime_event_persistence([_event()])
    report = build_runtime_event_persistence_report(simulation)
    checklist = build_runtime_event_persistence_checklist(report)

    assert checklist["readiness_status"] == READINESS_NOT_READY
    assert "PERSISTENCE_DISABLED_BY_POLICY" in checklist["blocking_items"]
    assert checklist["warnings"]


def test_checklist_is_review_required_when_checks_pass_but_approval_remains() -> None:
    checklist = build_runtime_event_persistence_checklist(_clean_report())

    assert checklist["readiness_status"] == READINESS_REVIEW_REQUIRED
    assert checklist["failed_checks"] == []
    assert checklist["blocking_items"] == []
    assert checklist["operator_review_required"] is True
    assert "APPROVAL_REQUIREMENTS_REMAIN" in checklist["warnings"]


def test_checklist_fails_secret_and_live_trading_dependency_checks() -> None:
    report = _clean_report()
    report["pcnrass_readiness_notes"] = ["api_key=SHOULD_NOT_APPEAR"]
    report["safety_assertions"] = []

    checklist = build_runtime_event_persistence_checklist(report)
    failed = {item["check_id"] for item in checklist["failed_checks"]}
    serialized = json.dumps(checklist, sort_keys=True)

    assert checklist["readiness_status"] == READINESS_NOT_READY
    assert "no_secrets_detected" in failed
    assert "no_live_trading_dependency" in failed
    assert "SHOULD_NOT_APPEAR" not in serialized


def test_checklist_api_route_is_read_only_and_does_not_mutate_bus() -> None:
    bus = RuntimeEventBus()
    bus.publish(_event())
    app = create_app(runtime_event_bus=bus)
    routes = {getattr(route, "path", "") for route in app.routes}
    checklist = get_runtime_event_persistence_checklist_payload(bus, limit=10)

    assert "/api/v1/runtime-event-persistence-checklist" in routes
    assert checklist["operator_review_required"] is True
    assert checklist["persistence_enabled"] is False
    assert checklist["writes_performed"] is False
    assert checklist["simulation_only"] is True
    assert len(bus.get_recent(10)) == 1
