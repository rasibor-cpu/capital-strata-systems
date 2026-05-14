from __future__ import annotations

import json

from dashboard.runtime.api_bridge import create_app as create_api_app
from dashboard.runtime.api_bridge import get_runtime_events_payload
from dashboard.runtime.runtime_event_bus import RuntimeEventBus, build_runtime_event
from dashboard.runtime.runtime_event_inspector import (
    DEFAULT_RUNTIME_EVENT_RETENTION_POLICY,
    MAX_RUNTIME_EVENT_EXPORT_LIMIT,
    RUNTIME_EVENT_INSPECTOR_VERSION,
    RuntimeEventRetentionPolicy,
    export_runtime_events,
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


def _seed_counted_bus(count: int) -> RuntimeEventBus:
    bus = RuntimeEventBus(max_recent=max(1, count + 5))
    for index in range(count):
        bus.publish(
            build_runtime_event(
                {
                    "event_type": "counted_event",
                    "sequence": index,
                    "api_token": "hide-me",
                },
                subsystem="test_events",
                severity="INFO" if index % 2 == 0 else "WARNING",
                correlation_id=f"COR-{index % 2}",
                source_module="tests.dashboard.test_runtime_event_inspector",
                timestamp_utc=f"2026-05-13T18:{index:02d}:00+00:00",
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
    assert payload["retention_policy"]["redaction_required"] is True
    assert payload["export_requested"] is False


def test_runtime_event_inspector_default_and_max_limit_policy() -> None:
    bus = _seed_counted_bus(6)
    policy = RuntimeEventRetentionPolicy(
        max_events=4,
        max_export_limit=2,
        default_inspection_limit=3,
    )

    default_payload = get_runtime_event_inspection_payload(bus, policy=policy)
    capped_payload = get_runtime_event_inspection_payload(bus, limit=99, policy=policy)

    assert default_payload["filters"]["limit"] == 3
    assert default_payload["total_returned"] == 3
    assert capped_payload["filters"]["limit"] == 4
    assert capped_payload["total_returned"] == 4
    assert capped_payload["summary"]["total_events"] == 4


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
    assert payload["redaction_applied"] is True


def test_runtime_event_export_is_read_only_json_safe_and_capped() -> None:
    bus = _seed_counted_bus(6)
    policy = RuntimeEventRetentionPolicy(
        max_events=6,
        max_export_limit=2,
        default_inspection_limit=4,
    )

    payload = export_runtime_events(bus, limit=99, policy=policy)
    serialized = json.dumps(payload, sort_keys=True)

    assert payload["export_requested"] is True
    assert payload["filters"]["limit"] == 2
    assert payload["total_returned"] == 2
    assert payload["export"]["allowed"] is True
    assert payload["export"]["format"] == "json"
    assert payload["export"]["event_count"] == 2
    assert payload["export"]["redaction_required"] is True
    assert "hide-me" not in serialized
    assert "REDACTED" in serialized


def test_runtime_event_export_empty_and_filtered_results() -> None:
    bus = _seed_bus()

    empty = export_runtime_events(None)
    filtered = export_runtime_events(
        bus,
        subsystem="alerting",
        correlation_id="COR-A",
        limit=MAX_RUNTIME_EVENT_EXPORT_LIMIT + 100,
    )

    assert empty["export_requested"] is True
    assert empty["export"]["event_count"] == 0
    assert empty["events"] == []
    assert filtered["filters"]["limit"] == DEFAULT_RUNTIME_EVENT_RETENTION_POLICY.max_export_limit
    assert filtered["total_returned"] == 1
    assert filtered["export"]["events"][0]["event_type"] == "broker_disconnect"


def test_runtime_event_export_can_be_policy_disabled_without_writes() -> None:
    bus = _seed_bus()
    policy = RuntimeEventRetentionPolicy(allow_export=False)

    payload = export_runtime_events(bus, policy=policy)

    assert payload["total_returned"] == 3
    assert payload["export"]["allowed"] is False
    assert payload["export"]["events"] == []
    assert payload["export"]["event_count"] == 0


def test_runtime_events_api_route_and_payload_are_read_only() -> None:
    bus = _seed_bus()
    app = create_api_app(runtime_event_bus=bus)
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_runtime_events_payload(bus, subsystem="alerting", limit=50)
    export_payload = get_runtime_events_payload(bus, export=True, limit=99999)

    assert "/api/v1/runtime-events" in routes
    assert payload["read_only"] is True
    assert payload["bus_available"] is True
    assert payload["total_returned"] == 1
    assert payload["filters"]["subsystem"] == "alerting"
    assert export_payload["export_requested"] is True
    assert export_payload["filters"]["limit"] == DEFAULT_RUNTIME_EVENT_RETENTION_POLICY.max_export_limit
    assert export_payload["export"]["format"] == "json"


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
