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
from dashboard.web.web_app import _dashboard_page


def _collect_paths(routes) -> set[str]:
    collected: set[str] = set()
    for route in routes:
        path = getattr(route, "path", None)
        if isinstance(path, str) and path:
            collected.add(path)
        nested = getattr(route, "routes", None)
        if nested:
            collected |= _collect_paths(nested)
        original_router = getattr(route, "original_router", None)
        original_routes = getattr(original_router, "routes", None)
        if original_routes:
            collected |= _collect_paths(original_routes)
    return collected


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
    assert payload["sections"]["positions"]["items"][0]["symbol"] == "BTC-USD"
    assert payload["sections"]["positions"]["long_count"] == 1
    assert payload["sections"]["positions"]["short_count"] == 1
    assert payload["sections"]["risk"]["risk_state"] == "NORMAL"
    assert payload["sections"]["governance"]["governance_enabled"] is True
    assert payload["sections"]["execution"]["execution_state"] == "READY"
    assert payload["sections"]["execution"]["recent_trade_count"] == 2
    assert payload["sections"]["execution"]["recent_trades"][0]["symbol"] == "BTC-USD"
    assert payload["sections"]["opportunities"]["count"] == 2
    assert payload["sections"]["opportunities"]["items"][0]["status"] == "MONITOR_ONLY"
    assert "portfolio_summary" in payload["sections"]
    assert "portfolio_greeks" in payload["sections"]


def test_api_bridge_routes_are_read_only_and_dashboard_state_fed() -> None:
    state = DashboardHydrationCoordinator().hydrate(**build_smoke_payloads())
    app = create_app(lambda: state)
    routes = _collect_paths(app.routes)

    required_routes = {
        "/api/v1/dashboard-state",
        "/api/v1/frontend-state",
        "/api/v1/account-summary",
        "/api/v1/positions",
        "/api/v1/risk",
        "/api/v1/governance",
        "/api/v1/opportunities",
        "/api/v1/broker",
        "/api/v1/broker-reconciliation",
        "/ws/v1/dashboard-state",
    }

    assert required_routes <= routes
    assert get_dashboard_state_payload(lambda: state)["session_id"] == "SMOKE-SESSION"
    assert get_frontend_payload(lambda: state)["sections"]["positions"]["total"] == 2
    assert (
        get_frontend_payload(lambda: state)["sections"]["broker_reconciliation"]["status"]
        == "BROKER_UNAVAILABLE"
    )
    assert build_section_payload(state, "risk")["data"]["risk_state"] == "NORMAL"


def test_missing_fields_use_frontend_safe_defaults() -> None:
    payload = build_frontend_payload({})

    assert payload["sections"]["account_summary"]["currency"] == "USD"
    assert payload["sections"]["positions"]["total"] == 0
    assert payload["sections"]["risk"]["gate_status"] == "OPEN"
    assert payload["sections"]["governance"]["audit_enabled"] is True
    assert payload["sections"]["market"]["trend_state"] == "UNKNOWN"
    assert payload["sections"]["execution"]["execution_state"] == "IDLE"
    assert payload["sections"]["portfolio_summary"]["portfolio_status"] == "NO_POSITIONS"
    assert payload["sections"]["portfolio_summary"]["total_exposure"] == 0.0
    assert payload["sections"]["portfolio_greeks"]["greeks_status"] == "NO_OPTIONS"
    assert payload["sections"]["portfolio_greeks"]["net_delta"] == 0.0
    assert json.dumps(payload)


def test_no_options_returns_greeks_zeroes_and_no_options_status() -> None:
    payloads = build_smoke_payloads()
    payloads["positions_payload"] = {
        "positions": [
            {
                "symbol": "BTC-USD",
                "asset_class": "CRYPTO",
                "side": "LONG",
                "qty": 0.1,
                "entry_price": 60000.0,
                "current_price": 61000.0,
                "unrealized_pnl": 100.0,
                "realized_pnl": 0.0,
            }
        ]
    }
    state = DashboardHydrationCoordinator().hydrate(**payloads)
    payload = build_frontend_payload(state)
    greeks = payload["sections"]["portfolio_greeks"]

    assert greeks["greeks_status"] == "NO_OPTIONS"
    assert greeks["delta"] == 0.0
    assert greeks["net_delta"] == 0.0
    assert greeks["options_exposure"] == 0.0


def test_source_failure_returns_source_unavailable(monkeypatch) -> None:
    from dashboard.runtime import frontend_contract as fc

    class _BrokenCorrelationEngine:
        def analyze_portfolio(self, positions):
            raise fc.PortfolioCorrelationEngineError("boom")

    monkeypatch.setattr(fc, "PortfolioCorrelationEngine", _BrokenCorrelationEngine)

    payload = build_frontend_payload(
        {
            "account_summary": {
                "cash_balance": 100000.0,
                "total_equity": 100000.0,
                "buying_power": 100000.0,
            },
            "pnl_summary": {"total_exposure": 1200.0},
            "position_state": {
                "positions": [
                    {
                        "symbol": "EUR_USD",
                        "asset_class": "FX",
                        "side": "LONG",
                        "exposure": 1200.0,
                    }
                ]
            },
        }
    )
    summary = payload["sections"]["portfolio_summary"]
    assert summary["portfolio_status"] == "SOURCE_UNAVAILABLE"
    assert summary["source"] == "SOURCE_UNAVAILABLE"

    payload_bad_greeks = build_frontend_payload(
        {
            "position_state": {
                "positions": "BAD_PAYLOAD_SHAPE",
            }
        }
    )
    greeks = payload_bad_greeks["sections"]["portfolio_greeks"]
    assert greeks["greeks_status"] == "SOURCE_UNAVAILABLE"
    assert greeks["source"] == "SOURCE_UNAVAILABLE"


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


def test_dashboard_html_renders_portfolio_health_and_greeks_status() -> None:
    html = _dashboard_page()
    assert "Portfolio Health" in html
    assert "Greeks Status" in html
