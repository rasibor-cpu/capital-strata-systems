from __future__ import annotations

import json

from dashboard.runtime.api_bridge import create_app as create_api_app
from dashboard.runtime.api_bridge import get_runtime_events_payload
from dashboard.runtime.runtime_event_bus import RuntimeEventBus, build_runtime_event
from dashboard.runtime.runtime_event_inspector import (
    RUNTIME_EVENT_INSPECTOR_VERSION,
    get_runtime_event_inspection_payload,
)
from dashboard.web.web_app import _css, _runtime_events_page, create_app as create_web_app


def _seed_bus() -> RuntimeEventBus:
    bus = RuntimeEventBus()
    bus.publish(
        build_runtime_event(
            {
                "event_type": "broker_disconnect",
                "password": "do-not-leak",
            },
            subsystem="alerting",
            severity="ERROR",
            correlation_id="COR-A",
            source_module="tests.dashboard.test_runtime_event_inspector",
            timestamp_utc="2026-05-13T18:00:00+00:00",
        )
    )
    bus.publish(
        build_runtime_event(
            {"event_type": "pnl_update", "net_pnl": 12.5},
            subsystem="pnl_summary",
            severity="INFO",
            correlation_id="COR-B",
            source_module="tests.dashboard.test_runtime_event_inspector",
            timestamp_utc="2026-05-13T18:01:00+00:00",
        )
    )
    bus.publish(
        build_runtime_event(
            {"event_type": "position_exit_booked", "symbol": "BTC-USD"},
            subsystem="trade_lifecycle",
            severity="WARNING",
            correlation_id="COR-A",
            source_module="tests.dashboard.test_runtime_event_inspector",
            timestamp_utc="2026-05-13T18:02:00+00:00",
        )
    )
    return bus


def test_runtime_event_inspector_empty_state_is_safe() -> None:
    payload = get_runtime_event_inspection_payload(None)

    assert payload["payload_version"] == RUNTIME_EVENT_INSPECTOR_VERSION
    assert payload["read_only"] is True
    assert payload["bus_available"] is False
    assert payload["empty"] is True
    assert payload["total_returned"] == 0
    assert payload["events"] == []
    assert payload["summary"]["total_events"] == 0


def test_runtime_event_inspector_filters_and_summarizes() -> None:
    bus = _seed_bus()

    alert_payload = get_runtime_event_inspection_payload(bus, subsystem="alerting")
    event_payload = get_runtime_event_inspection_payload(bus, event_type="pnl_update")
    severity_payload = get_runtime_event_inspection_payload(bus, severity="WARNING")
    correlation_payload = get_runtime_event_inspection_payload(bus, correlation_id="COR-A")

    assert alert_payload["total_returned"] == 1
    assert alert_payload["events"][0]["event_type"] == "broker_disconnect"
    assert event_payload["total_returned"] == 1
    assert event_payload["events"][0]["subsystem"] == "pnl_summary"
    assert severity_payload["total_returned"] == 1
    assert severity_payload["events"][0]["severity"] == "WARNING"
    assert correlation_payload["total_returned"] == 2
    assert correlation_payload["summary"]["counts_by_subsystem"]["alerting"] == 1
    assert correlation_payload["summary"]["counts_by_subsystem"]["trade_lifecycle"] == 1
    assert correlation_payload["summary"]["counts_by_event_type"]["broker_disconnect"] == 1
    assert correlation_payload["summary"]["counts_by_severity"]["ERROR"] == 1


def test_runtime_event_inspector_redacts_payloads_and_honors_limit() -> None:
    bus = _seed_bus()
    payload = get_runtime_event_inspection_payload(bus, limit=3)
    limited = get_runtime_event_inspection_payload(bus, limit=2)
    serialized = json.dumps(payload, sort_keys=True)

    assert limited["total_returned"] == 2
    assert limited["events"][0]["event_type"] == "pnl_update"
    assert limited["events"][1]["event_type"] == "position_exit_booked"
    assert "do-not-leak" not in serialized
    assert "REDACTED" in serialized


def test_runtime_events_api_route_and_payload_are_read_only() -> None:
    bus = _seed_bus()
    app = create_api_app(runtime_event_bus=bus)
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_runtime_events_payload(bus, subsystem="alerting", limit=50)

    assert "/api/v1/runtime-events" in routes
    assert payload["read_only"] is True
    assert payload["bus_available"] is True
    assert payload["total_returned"] == 1
    assert payload["filters"]["subsystem"] == "alerting"


def test_runtime_events_operator_page_route_and_markup() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _runtime_events_page()
    css = _css()

    assert "/runtime-events" in routes
    assert "/api/v1/runtime-events" in routes
    assert "CSS Runtime Events" in markup
    assert "Runtime Event Table" in markup
    assert "No runtime events match the current view" in markup
    assert "event-filter-event" in markup
    assert "event-filter-subsystem" in markup
    assert "event-filter-severity" in markup
    assert "event-filter-correlation" in markup
    assert "event-filter-limit" in markup
    assert 'fetch(`/api/v1/runtime-events?' in markup
    assert ".event-workspace" in css
    assert ".event-row" in css
