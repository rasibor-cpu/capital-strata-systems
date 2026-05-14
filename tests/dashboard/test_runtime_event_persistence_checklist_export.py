from __future__ import annotations

import json

from dashboard.runtime.api_bridge import (
    create_app,
    get_runtime_event_persistence_checklist_export_payload,
)
from dashboard.runtime.runtime_event_bus import RuntimeEventBus, build_runtime_event
from dashboard.runtime.runtime_event_persistence_checklist import (
    build_runtime_event_persistence_checklist,
)
from dashboard.runtime.runtime_event_persistence_checklist_export import (
    PERSISTENCE_CHECKLIST_SAFETY_DISCLAIMER,
    RUNTIME_EVENT_PERSISTENCE_CHECKLIST_EXPORT_VERSION,
    build_runtime_event_persistence_checklist_export,
)
from dashboard.runtime.runtime_event_persistence_report import (
    build_runtime_event_persistence_report,
)
from dashboard.runtime.runtime_event_persistence_simulator import (
    simulate_runtime_event_persistence,
)
from dashboard.web.web_app import (
    _css,
    _runtime_event_persistence_checklist_print_page,
    create_app as create_web_app,
)


def _event() -> dict[str, object]:
    return build_runtime_event(
        {"event_type": "alert_created", "message": "printable"},
        subsystem="alerting",
        severity="INFO",
        correlation_id="COR-CHECKLIST-EXPORT",
        source_module="tests.dashboard.test_runtime_event_persistence_checklist_export",
        timestamp_utc="2026-05-14T00:00:00+00:00",
    )


def _checklist() -> dict[str, object]:
    simulation = simulate_runtime_event_persistence([_event()])
    report = build_runtime_event_persistence_report(simulation)
    return build_runtime_event_persistence_checklist(report)


def test_checklist_export_object_is_json_safe_and_non_persistent() -> None:
    export = build_runtime_event_persistence_checklist_export(
        _checklist(),
        generated_at_utc="2026-05-14T00:10:00+00:00",
    )
    serialized = json.dumps(export, sort_keys=True)

    assert export["payload_version"] == RUNTIME_EVENT_PERSISTENCE_CHECKLIST_EXPORT_VERSION
    assert export["export_id"].startswith("EVCHECKEXPORT-")
    assert export["generated_at_utc"] == "2026-05-14T00:10:00+00:00"
    assert export["operator_review_required"] is True
    assert export["persistence_enabled"] is False
    assert export["writes_performed"] is False
    assert export["simulation_only"] is True
    assert export["read_only"] is True
    assert export["export_format"] == "json"
    assert PERSISTENCE_CHECKLIST_SAFETY_DISCLAIMER in export["safety_disclaimer"]
    assert "secret=" not in serialized.lower()


def test_checklist_export_redacts_sensitive_review_strings() -> None:
    checklist = _checklist()
    checklist["warnings"] = ["api_key=SHOULD_NOT_APPEAR"]
    checklist["failed_checks"] = [
        {"check_id": "token=SHOULD_NOT_APPEAR", "label": "password=NOPE", "status": "FAIL"}
    ]
    export = build_runtime_event_persistence_checklist_export(checklist)
    serialized = json.dumps(export, sort_keys=True)

    assert "SHOULD_NOT_APPEAR" not in serialized
    assert "password=NOPE" not in serialized
    assert "REDACTED" in serialized


def test_checklist_export_api_route_is_read_only_and_does_not_mutate_bus() -> None:
    bus = RuntimeEventBus()
    bus.publish(_event())
    app = create_app(runtime_event_bus=bus)
    routes = {getattr(route, "path", "") for route in app.routes}
    export = get_runtime_event_persistence_checklist_export_payload(bus, limit=10)

    assert "/api/v1/runtime-event-persistence-checklist-export" in routes
    assert export["operator_review_required"] is True
    assert export["persistence_enabled"] is False
    assert export["writes_performed"] is False
    assert export["simulation_only"] is True
    assert len(bus.get_recent(10)) == 1


def test_checklist_print_view_route_and_markup_are_safe() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _runtime_event_persistence_checklist_print_page()

    assert "/runtime-event-persistence-checklist-print" in routes
    assert "/api/v1/runtime-event-persistence-checklist-export" in routes
    assert "CSS Persistence Checklist Print View" in markup
    assert "Persistence Checklist Print View" in markup
    assert "Persistence remains disabled" in markup
    assert "No approval action" in markup
    assert "Required Checks" in markup
    assert "Passed Checks" in markup
    assert "Failed Checks" in markup
    assert "Blocking Items" in markup
    assert "Warnings" in markup
    assert "window.print()" in markup


def test_checklist_print_view_has_lightweight_print_css() -> None:
    css = _css()

    assert ".print-workspace" in css
    assert ".print-summary-row" in css
    assert "@media print" in css
    assert ".print-shell" in css
    assert "100vw" in css
    assert "#print-disclaimer" in css
    assert "word-break: break-word" in css
    assert ".print-controls" in css
    assert "display: none !important" in css
