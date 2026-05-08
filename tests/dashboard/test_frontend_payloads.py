from __future__ import annotations

import json
import time
from decimal import Decimal

from dashboard.runtime.api_bridge import (
    create_app,
    get_dashboard_state_payload,
    get_frontend_payload,
)
from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.dashboard_state import DashboardState
from dashboard.runtime.frontend_contract import (
    FRONTEND_SECTIONS,
    build_frontend_payload,
    build_section_payload,
)
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads
from dashboard.runtime.ws_bridge import (
    WS_DELTA_SECTIONS,
    build_delta_ws_message,
    build_heartbeat_ws_message,
    build_initial_ws_message,
)


def test_dashboard_state_to_dict_is_json_safe_and_redacted() -> None:
    state = DashboardState(session_id="TEST-SESSION", user_id="00017")
    state.last_scan_results["account_summary"] = {
        "cash_balance": Decimal("1234.56"),
        "api_key": "SHOULD_NOT_LEAK",
        "nested": {
            "token": "SHOULD_NOT_LEAK",
            "safe_value": Decimal("7.25"),
        },
    }

    payload = state.to_dict()
    encoded = json.dumps(payload)

    assert payload["payload_version"] == "1.0.0"
    assert payload["payload_schema"] == "css.dashboard.frontend.v1"
    assert payload["session_identifier"] == "TEST-SESSION"
    assert payload["source_metadata"]["secrets_redacted"] is True
    assert payload["account_summary"]["cash_balance"] == "1234.56"
    assert payload["account_summary"]["api_key"] == "REDACTED"
    assert payload["account_summary"]["nested"]["token"] == "REDACTED"
    assert "SHOULD_NOT_LEAK" not in encoded


def test_frontend_payload_schema_integrity_and_size() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())

    started = time.perf_counter()
    payload = build_frontend_payload(state)
    elapsed_ms = (time.perf_counter() - started) * 1000
    encoded = json.dumps(payload)

    assert elapsed_ms < 100.0
    assert len(encoded.encode("utf-8")) < 65536
    assert payload["payload_schema"] == "css.frontend.contract.v1"
    assert set(FRONTEND_SECTIONS) <= set(payload["sections"])
    assert payload["sections"]["account_summary"]["currency"] == "USD"
    assert payload["sections"]["positions"]["total"] == 2
    assert payload["sections"]["risk"]["risk_state"] == "NORMAL"
    assert payload["sections"]["governance"]["governance_enabled"] is True
    assert payload["sections"]["execution"]["execution_state"] == "READY"


def test_api_bridge_routes_are_read_only_and_dashboard_state_fed() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    app = create_app(lambda: state)
    routes = {getattr(route, "path", "") for route in app.routes}

    required_routes = {
        "/api/v1/dashboard-state",
        "/api/v1/frontend-state",
        "/api/v1/account-summary",
        "/api/v1/positions",
        "/api/v1/risk",
        "/api/v1/governance",
        "/api/v1/opportunities",
        "/api/v1/broker",
        "/ws/v1/dashboard-state",
    }

    assert required_routes <= routes
    assert get_dashboard_state_payload(lambda: state)["session_id"] == "SMOKE-SESSION"
    assert get_frontend_payload(lambda: state)["sections"]["positions"]["total"] == 2
    assert build_section_payload(state, "risk")["data"]["risk_state"] == "NORMAL"


def test_missing_fields_use_frontend_safe_defaults() -> None:
    payload = build_frontend_payload({})

    assert payload["sections"]["account_summary"]["currency"] == "USD"
    assert payload["sections"]["positions"]["total"] == 0
    assert payload["sections"]["risk"]["gate_status"] == "OPEN"
    assert payload["sections"]["governance"]["audit_enabled"] is True
    assert payload["sections"]["market"]["trend_state"] == "UNKNOWN"
    assert payload["sections"]["execution"]["execution_state"] == "IDLE"
    assert json.dumps(payload)


def test_websocket_snapshot_delta_and_heartbeat_payloads_are_stable() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    initial = build_initial_ws_message(state, sequence=1)

    updated = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    updated.last_scan_results["pnl_summary"] = {
        **updated.last_scan_results["pnl_summary"],
        "net_pnl": 99.25,
    }

    delta = build_delta_ws_message(initial, updated, sequence=2)
    heartbeat = build_heartbeat_ws_message(sequence=3)

    assert initial["message_type"] == "dashboard_snapshot"
    assert delta["message_type"] == "dashboard_delta"
    assert "pnl_summary" in delta["changed_sections"]
    assert set(delta["changed_sections"]) <= set(WS_DELTA_SECTIONS)
    assert heartbeat["message_type"] == "dashboard_heartbeat"
    assert heartbeat["changed_sections"] == []
    assert json.dumps(initial)
    assert json.dumps(delta)
    assert json.dumps(heartbeat)
