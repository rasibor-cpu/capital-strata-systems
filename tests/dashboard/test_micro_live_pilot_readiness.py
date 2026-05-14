from __future__ import annotations

import json

from dashboard.runtime.api_bridge import (
    create_app,
    get_micro_live_pilot_readiness_payload,
)
from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator
from dashboard.runtime.micro_live_pilot_readiness import (
    MICRO_LIVE_PILOT_READINESS_PAYLOAD_VERSION,
    PILOT_LIMITED_READY,
    PILOT_NOT_READY,
    PILOT_REVIEW_REQUIRED,
    build_micro_live_pilot_readiness_payload,
)
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads
from dashboard.web.web_app import _css, _micro_live_pilot_readiness_page, create_app as create_web_app


def _dashboard_payload() -> dict:
    return {
        "resolved_mode": "live",
        "live_or_paper": "live",
        "session": {
            "session_id": "PILOT-SESSION",
            "live_or_paper": "live",
            "resolved_mode": "live",
        },
        "broker_summary": {
            "selected_broker": "coinbase",
            "broker_mode": "live",
            "connected": True,
            "missing_credentials": False,
            "readiness_status": "BROKER_READY",
            "account_readiness": "LIVE_READY",
        },
        "governance_summary": {
            "audit_enabled": True,
            "unified_trade_gate_active": True,
        },
    }


def _certification(status: str = "LIVE_DRY_RUN_CERTIFIED") -> dict:
    return {
        "payload_version": "css.broker_live_dry_run_certification.v1",
        "broker": "coinbase",
        "mode": "live",
        "status": status,
        "certified_for_live": status == "LIVE_DRY_RUN_CERTIFIED",
        "order_probe_status": "DRY_RUN_ACKNOWLEDGED",
    }


def _persistence_checklist() -> dict:
    return {
        "payload_version": "css.runtime_event_persistence_checklist.v1",
        "persistence_enabled": False,
        "writes_performed": False,
        "simulation_only": True,
    }


def _pilot_order() -> dict:
    return {
        "broker": "coinbase",
        "symbol": "BTC-USD",
        "asset_class": "crypto",
        "currency": "CAD",
        "capital": "15.00",
        "order_type": "limit",
        "live_order_count": 1,
        "max_slippage_pct": "0.35",
    }


def test_micro_live_pilot_readiness_defaults_to_not_ready() -> None:
    payload = build_micro_live_pilot_readiness_payload({})
    failed_codes = {item["check_id"] for item in payload["failed_checks"]}

    assert payload["payload_version"] == MICRO_LIVE_PILOT_READINESS_PAYLOAD_VERSION
    assert payload["overall_status"] == PILOT_NOT_READY
    assert payload["persistence_enabled"] is False
    assert payload["writes_performed"] is False
    assert payload["automatic_live_execution_enabled"] is False
    assert payload["unrestricted_live_trading_enabled"] is False
    assert "live_readiness_certification_present" in failed_codes
    assert "broker_ready" in failed_codes


def test_micro_live_pilot_can_be_limited_ready_with_all_evidence() -> None:
    payload = build_micro_live_pilot_readiness_payload(
        _dashboard_payload(),
        live_readiness_certification=_certification(),
        persistence_checklist=_persistence_checklist(),
        pcnrass_summary={"passed": True},
        operator_review_completed=True,
        pilot_order=_pilot_order(),
    )

    assert payload["overall_status"] == PILOT_LIMITED_READY
    assert payload["failed_checks"] == []
    assert payload["blockers"] == []
    assert payload["allowed_broker_targets"] == ["Coinbase Advanced"]
    assert payload["allowed_symbols"] == ["BTC-USD"]
    assert payload["max_pilot_capital"]["display"] == "CAD $15"
    assert "Limit orders only" in payload["live_restrictions"]


def test_micro_live_pilot_requires_operator_review_and_pcnrass() -> None:
    payload = build_micro_live_pilot_readiness_payload(
        _dashboard_payload(),
        live_readiness_certification=_certification(),
        persistence_checklist=_persistence_checklist(),
        pcnrass_summary={"passed": False},
        operator_review_completed=False,
        pilot_order=_pilot_order(),
    )
    failed_codes = {item["check_id"] for item in payload["failed_checks"]}

    assert payload["overall_status"] == PILOT_REVIEW_REQUIRED
    assert payload["blockers"] == []
    assert "operator_review_completed" in failed_codes
    assert "pcnrass_validation_passed" in failed_codes


def test_micro_live_pilot_blocker_handling_fails_closed() -> None:
    payload = build_micro_live_pilot_readiness_payload(
        _dashboard_payload(),
        live_readiness_certification=_certification("LIVE_DRY_RUN_BLOCKED"),
        persistence_checklist=_persistence_checklist(),
        pcnrass_summary={"passed": True},
        operator_review_completed=True,
        pilot_order={**_pilot_order(), "symbol": "ETH-USD"},
    )
    failed_codes = {item["check_id"] for item in payload["failed_checks"]}

    assert payload["overall_status"] == PILOT_NOT_READY
    assert payload["blockers"]
    assert "live_readiness_certified" in failed_codes
    assert "pilot_order_within_constraints" in failed_codes


def test_micro_live_pilot_payload_is_redaction_safe() -> None:
    payload = build_micro_live_pilot_readiness_payload(
        _dashboard_payload(),
        live_readiness_certification={
            **_certification(),
            "api_key": "SHOULD_NOT_LEAK",
        },
        persistence_checklist=_persistence_checklist(),
        pcnrass_summary={"passed": True},
        operator_review_completed=True,
        pilot_order={**_pilot_order(), "note": "token=SHOULD_NOT_LEAK"},
    )
    encoded = json.dumps(payload, sort_keys=True)

    assert "SHOULD_NOT_LEAK" not in encoded
    assert "REDACTED" in encoded


def test_micro_live_pilot_api_route_is_read_only_and_fail_closed() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    app = create_app(lambda: state)
    routes = {getattr(route, "path", "") for route in app.routes}
    payload = get_micro_live_pilot_readiness_payload(lambda: state)

    assert "/api/v1/micro-live-pilot-readiness" in routes
    assert payload["overall_status"] == PILOT_NOT_READY
    assert payload["readiness_review_only"] is True
    assert payload["automatic_live_execution_enabled"] is False
    assert payload["persistence_enabled"] is False


def test_micro_live_pilot_operator_ui_renders_restrictions() -> None:
    app = create_web_app()
    routes = {getattr(route, "path", "") for route in app.routes}
    markup = _micro_live_pilot_readiness_page()
    css = _css()

    assert "/micro-live-pilot-readiness" in routes
    assert "Controlled Micro-Live Pilot Readiness" in markup
    assert "Readiness review only" in markup
    assert "No live order action" in markup
    assert "No approval grant" in markup
    assert "Approved Pilot Constraints" in markup
    assert "Live Restrictions" in markup
    assert "Coinbase Advanced" in markup
    assert "BTC-USD" in markup
    assert "CAD $15" in markup
    assert "/api/v1/micro-live-pilot-readiness" in markup
    assert ".pilot-workspace" in css
    assert ".pilot-summary-row" in css
