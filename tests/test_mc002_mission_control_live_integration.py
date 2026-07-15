from __future__ import annotations

from math import inf

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard.mission_control import build_live_mission_control_state, build_mission_control_state, register_mission_control
from dashboard.mission_control.contracts import MISSION_CONTROL_SCHEMA_VERSION, validate_mission_control_state
from dashboard.mission_control.freshness import build_freshness_summary
from dashboard.mission_control.host_registration import MISSION_CONTROL_HOST_MARKER
from dashboard.mission_control.navigation import MISSION_CONTROL_SECTIONS
from dashboard.mission_control.permissions import mission_control_permissions_payload, validate_read_only_permissions
from dashboard.mission_control.routes import create_mission_control_router
from dashboard.mission_control.serializers import deterministic_json
from dashboard.mission_control.source_registry import build_source_registry
from dashboard.runtime.dashboard_state import BrokerState, DashboardState, GovernanceState, MarketStatePayload
from dashboard.web.web_app import create_app as create_web_app


def _runtime_state() -> DashboardState:
    return DashboardState(
        session_id="mc002-session",
        user_id="operator",
        role="RISK_MANAGER",
        cycle_number=44,
        engine_mode="SAFE",
        live_or_paper="paper",
        broker_state=BrokerState(
            selected_broker="COINBASE",
            broker_mode="paper",
            connected=True,
            live_trading_enabled=False,
            last_heartbeat="2026-07-15T12:00:00+00:00",
            api_health="GREEN",
            supported_assets=["CRYPTO"],
            account_readiness="PASS",
            latency_ms=42.0,
            readiness_status="READ_ONLY_READY",
            runtime_certification_snapshot={
                "certification": "GREEN",
                "operational_state": "READ_ONLY",
                "generated_at": "2026-07-15T12:00:01+00:00",
                "blocker_reasons": [],
                "warning_reasons": [],
            },
        ),
        governance_state=GovernanceState(
            governance_enabled=True,
            unified_trade_gate_active=True,
            audit_enabled=True,
        ),
        global_market_state=MarketStatePayload(
            trend_state="UP",
            volatility_state="LOW",
            liquidity_state="GOOD",
            regime_state="RISK_ON",
        ),
        last_scan_results={
            "account_summary": {
                "cash_balance": 2500.0,
                "total_equity": 3000.0,
                "buying_power": 2500.0,
                "margin_used": 0.0,
                "available_margin": 2500.0,
                "currency": "USD",
                "broker": "COINBASE",
                "account_mode": "paper",
            },
            "pnl_summary": {
                "realized_pnl": 12.5,
                "unrealized_pnl": -1.25,
                "net_pnl": 11.25,
                "total_exposure": 100.0,
            },
            "risk_summary": {
                "risk_state": "GREEN",
                "risk_score": 12.0,
                "limit_breaches": [],
                "warnings": [],
                "total_exposure": 100.0,
                "current_drawdown": 0.0,
            },
            "execution_summary": {
                "execution_state": "BLOCKED",
                "accepted_trades": 0,
                "rejected_trades": 1,
                "avg_slippage": 0.0,
                "fee_cost": 0.0,
            },
            "position_state": {
                "open_count": 1,
                "total_exposure": 100.0,
                "active_symbols": ["BTC-USD"],
                "positions": [
                    {
                        "symbol": "BTC-USD",
                        "asset_class": "CRYPTO",
                        "side": "LONG",
                        "qty": 0.001,
                        "entry_price": 100000.0,
                        "current_price": 100000.0,
                        "exposure": 100.0,
                        "realized_pnl": 0.0,
                        "unrealized_pnl": 0.0,
                    }
                ],
            },
            "opportunities": [
                {
                    "symbol": "BTC-USD",
                    "asset_class": "CRYPTO",
                    "signal": "MONITOR",
                    "status": "ADVISORY_ONLY",
                }
            ],
            "options_income": {"status": "PAPER_READY", "opportunities": []},
            "alerts": {"active": [], "count": 0, "severity": "GREEN", "incident_timeline": []},
            "analytics_summary": {"headline": {"expectancy": 0.2, "profit_factor": 1.4}},
        },
    )


def test_mc002_web_host_registers_mission_control_with_existing_provider() -> None:
    client = TestClient(create_web_app(lambda: _runtime_state()))

    state_response = client.get("/mission-control/api/state")
    page_response = client.get("/mission-control/executive-overview")
    health_response = client.get("/mission-control/api/health")

    assert state_response.status_code == 200
    assert page_response.status_code == 200
    assert health_response.status_code == 200
    state = state_response.json()
    assert state["schema_version"] == MISSION_CONTROL_SCHEMA_VERSION
    assert state["mock_data"] is False
    assert state["platform"]["selected_broker"] == "COINBASE"
    assert state["portfolio"]["equity"] == 3000.0
    assert state["source_registry"]["runtime"]["source"] == "RUNTIME"
    assert state["safety"]["execution_allowed"] is False
    assert state["safety"]["live_trading_blocked"] is True


def test_mc002_host_registration_is_idempotent_and_rejects_conflicts() -> None:
    app = FastAPI()
    register_mission_control(app, lambda: _runtime_state())
    first_count = len(app.router.routes)
    register_mission_control(app, lambda: _runtime_state())

    assert getattr(app.state, MISSION_CONTROL_HOST_MARKER) is True
    assert len(app.router.routes) == first_count

    conflicting = FastAPI()

    @conflicting.get("/mission-control/custom")
    def custom() -> dict[str, bool]:
        return {"ok": True}

    with pytest.raises(RuntimeError, match="mission_control_route_prefix_conflict"):
        register_mission_control(conflicting, lambda: _runtime_state())


def test_mc002_routes_are_get_only_and_have_api_prefixes() -> None:
    router = create_mission_control_router(lambda: _runtime_state())
    paths = {route.path: set(route.methods or set()) for route in router.routes}

    assert "/mission-control/api/state" in paths
    assert "/mission-control/api/health" in paths
    assert "/mission-control/api/navigation" in paths
    assert "/mission-control/api/brokers" in paths
    assert "/mission-control/api/certification" in paths
    assert all(methods <= {"GET", "HEAD"} for methods in paths.values())


def test_mc002_all_pages_render_from_runtime_state_without_mock_label() -> None:
    client = TestClient(create_web_app(lambda: _runtime_state()))

    for section in MISSION_CONTROL_SECTIONS:
        response = client.get(section.route)
        assert response.status_code == 200
        assert section.label in response.text
        assert "MOCK DATA - NOT LIVE" not in response.text
        assert "No execution authority is granted" in response.text


def test_mc002_live_state_adapter_adds_health_and_state_hash() -> None:
    state = build_live_mission_control_state(_runtime_state())

    assert state["state_hash"]
    assert state["health"]["read_only"] is True
    assert state["health"]["execution_allowed"] is False
    assert state["data_sources"]["brokers"]["source"] == "RUNTIME"
    assert state["freshness"]["overall_freshness"] in {"FRESH", "AGING", "STALE", "UNAVAILABLE", "UNKNOWN"}


def test_mc002_unavailable_canonical_state_does_not_silently_use_mock_data() -> None:
    state = build_mission_control_state(None, allow_mock=False)

    assert state["mock_data"] is False
    assert state["source_registry"]["runtime"]["source"] == "UNAVAILABLE"
    assert state["source_registry"]["portfolio"]["source"] == "UNAVAILABLE"
    assert state["platform"]["platform_status"] in {"UNAVAILABLE", "FAIL_CLOSED"}


def test_mc002_freshness_downgrades_stale_mandatory_data() -> None:
    registry = {
        "runtime": {
            "source": "RUNTIME",
            "generated_at": "2026-07-15T11:00:00+00:00",
            "observed_at": "2026-07-15T11:00:00+00:00",
        },
        "brokers": {
            "source": "UNAVAILABLE",
            "generated_at": "UNAVAILABLE",
            "observed_at": "UNAVAILABLE",
            "unavailable_reason": "broker_snapshot_missing",
        },
    }

    summary = build_freshness_summary(registry)

    assert summary["stale_mandatory_data"] is True
    assert "brokers" in summary["stale_mandatory_sections"]


def test_mc002_source_registry_preserves_provenance_and_stable_sources() -> None:
    state = build_mission_control_state(_runtime_state(), allow_mock=False)
    registry = build_source_registry(
        {"mission_control_data_source": "RUNTIME", "generated_at": state["generated_at"]},
        state,
        dashboard_state_available=True,
        allow_mock=False,
    )

    assert registry["platform"]["source"] == "RUNTIME"
    assert registry["certification"]["source_module"] == "backend.runtime.runtime_certification_snapshot"
    assert registry["brokers"]["source_module"] == "backend.runtime.canonical_broker_runtime_state"


def test_mc002_read_only_permissions_are_enforced() -> None:
    permissions = mission_control_permissions_payload()
    ok, reasons = validate_read_only_permissions(permissions)
    unsafe = dict(permissions)
    unsafe["can_execute"] = True

    unsafe_ok, unsafe_reasons = validate_read_only_permissions(unsafe)

    assert ok is True, reasons
    assert unsafe_ok is False
    assert "permission_invalid:can_execute" in unsafe_reasons


def test_mc002_contract_rejects_secret_non_finite_and_write_capable_payloads() -> None:
    state = build_mission_control_state(_runtime_state(), allow_mock=False)
    bad = dict(state)
    bad["configuration"] = {"api_key": "should-not-render"}
    bad["portfolio"] = {"equity": inf}
    bad["permissions"] = {**state["permissions"], "can_change_broker": True}

    validation = validate_mission_control_state(bad)

    assert validation["valid"] is False
    assert any(reason.startswith("secret_bearing_field") for reason in validation["reasons"])
    assert any(reason.startswith("non_finite_value") for reason in validation["reasons"])
    assert "permission_invalid:can_change_broker" in validation["reasons"]


def test_mc002_serialization_is_deterministic_and_contains_no_execution_controls() -> None:
    state = build_mission_control_state(_runtime_state(), allow_mock=False)
    encoded_a = deterministic_json(state)
    encoded_b = deterministic_json(state)

    assert encoded_a == encoded_b
    assert "submit_order" not in encoded_a
    assert "cancel_order" not in encoded_a
    assert "credential_entry" not in encoded_a
