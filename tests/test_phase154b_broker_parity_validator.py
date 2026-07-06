from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from backend.runtime.broker_parity_validator import validate_broker_parity
from backend.runtime.broker_readiness_framework import (
    BROKER_PARITY_COMPARABLE_FIELDS,
    broker_readiness_payload,
    build_broker_readiness_snapshot,
)
from backend.runtime.live_execution_authority import evaluate_live_execution_authority
import backend.runtime.live_execution_authority as live_execution_authority
from backend.runtime.live_readiness_state_machine import evaluate_live_readiness_state
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.dashboard_hydration_coordinator import DashboardHydrationCoordinator
from dashboard.runtime.frontend_contract import build_frontend_payload
from launcher.css_mobile_launcher import app as launcher_app


def _ready_readiness(broker_name: str, broker_type: str, *, execution_enabled: bool = False) -> dict[str, object]:
    return broker_readiness_payload(
        build_broker_readiness_snapshot(
            {
                "broker_name": broker_name,
                "broker_type": broker_type,
                "mode": "live",
                "credential_status": "PRESENT",
                "authenticated": True,
                "connected": True,
                "account_loaded": True,
                "market_data_ready": True,
                "products_loaded": 2,
                "broker_health": "HEALTHY",
                "infrastructure_health": "HEALTHY",
                "credentials_health": "READY",
                "authentication_health": "AUTHENTICATED",
                "connection_health": "CONNECTED",
                "market_data_health": "READY",
                "account_data_health": "READY",
                "execution_supported": True,
                "execution_enabled": execution_enabled,
                "account_balance": 100.0,
                "equity": 100.0,
                "buying_power": 90.0,
            }
        )
    )


def test_phase154b_validator_passes_for_identical_canonical_readiness_behavior() -> None:
    report = validate_broker_parity(
        _ready_readiness("COINBASE", "CRYPTO"),
        _ready_readiness("OANDA", "FX"),
    )

    assert report["parity_status"] == "PASS"
    assert report["mismatched_fields"] == []
    assert report["authority_parity"] is True
    assert report["fail_closed_parity"] is True
    assert report["execution_allowed"] is False
    assert set(report["comparable_fields"]) == set(BROKER_PARITY_COMPARABLE_FIELDS)


def test_phase154b_validator_reports_mismatched_canonical_fields() -> None:
    coinbase = _ready_readiness("COINBASE", "CRYPTO")
    oanda = _ready_readiness("OANDA", "FX")
    oanda["market_data_ready"] = False

    report = validate_broker_parity(coinbase, oanda)

    assert report["parity_status"] == "REVIEW"
    assert any(item["field"] == "market_data_ready" for item in report["mismatched_fields"])


def test_phase154b_fail_closed_scenarios_are_identical_for_coinbase_and_oanda() -> None:
    report = validate_broker_parity()

    for name in (
        "missing_credentials",
        "authentication_failed",
        "broker_execution_disabled",
        "pilot_disarmed",
    ):
        scenario = report["scenario_results"][name]
        assert scenario["authority_parity"] is True
        assert scenario["fail_closed_parity"] is True
        assert scenario["coinbase_authority"]["execution_authority"] is False
        assert scenario["oanda_authority"]["execution_authority"] is False
        assert scenario["coinbase_authority"]["can_live_execute"] is False
        assert scenario["oanda_authority"]["can_live_execute"] is False


def test_phase154b_live_execution_authority_never_branches_on_broker_name() -> None:
    source = inspect.getsource(live_execution_authority)

    assert "COINBASE" not in source
    assert "OANDA" not in source
    assert "IBKR" not in source


def test_phase154b_authority_and_readiness_state_match_for_both_brokers() -> None:
    coinbase = {"broker_readiness": _ready_readiness("COINBASE", "CRYPTO")}
    oanda = {"broker_readiness": _ready_readiness("OANDA", "FX")}

    coinbase_authority = evaluate_live_execution_authority(
        {
            **coinbase,
            "operator_requested_live": True,
            "live_micro_pilot_state": "ARMED",
            "capital_governor": "PASS",
            "unified_trade_gate": "PASS",
            "margin_gate": "PASS",
            "anti_bleed_guard": "PASS",
            "rbac": "PASS",
            "kill_switch": "CLEAR",
            "go_no_go": "GO",
        }
    )
    oanda_authority = evaluate_live_execution_authority(
        {
            **oanda,
            "operator_requested_live": True,
            "live_micro_pilot_state": "ARMED",
            "capital_governor": "PASS",
            "unified_trade_gate": "PASS",
            "margin_gate": "PASS",
            "anti_bleed_guard": "PASS",
            "rbac": "PASS",
            "kill_switch": "CLEAR",
            "go_no_go": "GO",
        }
    )
    assert coinbase_authority.as_dict() == oanda_authority.as_dict()

    assert evaluate_live_readiness_state(coinbase).readiness_state == evaluate_live_readiness_state(oanda).readiness_state


def test_phase154b_frontend_and_dashboard_api_publish_broker_parity() -> None:
    state = DashboardHydrationCoordinator().hydrate(
        broker_payload={
            "selected_broker": "COINBASE",
            "broker_readiness": _ready_readiness("COINBASE", "CRYPTO"),
        }
    )

    frontend = build_frontend_payload(state)
    assert "broker_parity" in frontend["sections"]
    assert frontend["sections"]["broker_parity"]["authority_parity"] is True
    assert frontend["sections"]["broker_parity"]["execution_allowed"] is False

    client = TestClient(create_app(lambda: state))
    response = client.get("/api/v1/broker-parity")
    assert response.status_code == 200
    assert response.json()["section"] == "broker_parity"
    assert response.json()["data"]["fail_closed_parity"] is True


def test_phase154b_launcher_exposes_broker_parity_route_and_panel() -> None:
    client = TestClient(launcher_app)

    response = client.get("/api/v1/broker-parity")
    assert response.status_code == 200
    payload = response.json()
    assert payload["section"] == "broker_parity"
    assert payload["data"]["execution_allowed"] is False
    assert payload["data"]["authority_parity"] is True

    page = client.get("/mobile")
    assert page.status_code == 200
    assert "Broker Parity Status" in page.text
    assert "Authority Parity" in page.text
    assert "Fail-Closed Parity" in page.text
