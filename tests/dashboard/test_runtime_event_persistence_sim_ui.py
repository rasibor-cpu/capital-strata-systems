from __future__ import annotations

from dashboard.web.web_app import (
    _css,
    _runtime_event_persistence_sim_page,
    create_app,
)


def test_persistence_sim_page_registers_read_only_route_and_markup() -> None:
    app = create_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _runtime_event_persistence_sim_page()

    assert "/runtime-event-persistence-sim" in routes
    assert "/api/v1/runtime-event-persistence-checklist" in routes
    assert "/api/v1/runtime-event-persistence-sim" in routes
    assert "/api/v1/runtime-event-persistence-scenarios" in routes
    assert "/api/v1/runtime-event-persistence-report" in routes
    assert "CSS Runtime Event Persistence Simulator" in markup
    assert "Persistence Simulation Results" in markup
    assert "Rejection Reasons" in markup
    assert "Subsystem Breakdown" in markup
    assert "Simulation Warnings" in markup
    assert "Backend Recommendation" in markup
    assert "Storage Backend Comparison" in markup
    assert "Governance Blockers" in markup
    assert "Persistence Dry-Run Report" in markup
    assert "Report Safety Assertions" in markup
    assert "Approval Requirements" in markup
    assert "Operator Approval Checklist" in markup
    assert "Checklist Failed Checks" in markup
    assert "Checklist Warnings" in markup
    assert "data-refresh-sim" in markup


def test_persistence_sim_page_exposes_summary_and_empty_state() -> None:
    markup = _runtime_event_persistence_sim_page()

    expected = [
        "SIMULATION ONLY - persistence remains disabled",
        "Accepted",
        "Rejected",
        "Estimated Bytes",
        "Event Rate",
        "Inspected",
        "Writes",
        "Recommended",
        "Storage Estimate",
        "Queryability",
        "Risk",
        "Report ID",
        "Simulation Only",
        "Persistence Enabled",
        "Export Format",
        "Readiness",
        "Review Required",
        "Passed",
        "Failed",
        "No persistence simulation events match the current view",
        "No storage backend scenario data",
        "<span>Index</span><span>Event</span><span>Subsystem</span>",
        "<span>Decision</span><span>Reasons</span><span>Correlation</span>",
    ]

    for item in expected:
        assert item in markup


def test_persistence_sim_page_uses_safe_filter_query() -> None:
    markup = _runtime_event_persistence_sim_page()

    assert 'value="100"' in markup
    assert 'max="1000"' in markup
    assert 'value="15"' in markup
    assert 'max="60"' in markup
    assert 'params.set("event_type", eventType)' in markup
    assert 'params.set("subsystem", subsystem)' in markup
    assert 'params.set("severity", severity)' in markup
    assert 'params.set("correlation_id", correlation)' in markup
    assert 'params.set("limit", limit)' in markup
    assert 'params.set("requested_window_minutes", windowMinutes)' in markup
    assert "hydrateSimFiltersFromLocation" in markup
    assert '["requested_window_minutes", "sim-filter-window"]' in markup
    assert 'fetch(`/api/v1/runtime-event-persistence-sim?' in markup
    assert 'fetch(`/api/v1/runtime-event-persistence-checklist?' in markup
    assert 'fetch(`/api/v1/runtime-event-persistence-scenarios?' in markup
    assert 'fetch(`/api/v1/runtime-event-persistence-report?' in markup


def test_persistence_sim_page_preserves_simulation_only_flags() -> None:
    markup = _runtime_event_persistence_sim_page()

    assert "payload.simulation_only" in markup
    assert "payload.persistence_enabled" in markup
    assert "payload.writes_performed" in markup
    assert "Persistence disabled" in markup
    assert "NO_WRITES_PERFORMED" in markup
    assert "scenario_report" in markup
    assert "backend_comparison" in markup
    assert "payload.safety_assertions" in markup
    assert "payload.remaining_approval_requirements" in markup
    assert "payload.operator_review_required" in markup
    assert "payload.readiness_status" in markup


def test_persistence_sim_layout_is_mobile_safe() -> None:
    css = _css()

    assert ".sim-workspace" in css
    assert ".sim-row" in css
    assert ".sim-backend-row" in css
    assert ".sim-controls label" in css
    assert ".sim-controls input" in css
    assert ".sim-banner" in css
    assert ".app-nav a {\n    flex: 1 1 100%;" in css
    assert "calc(100vw - 28px)" not in css
