from __future__ import annotations

from backend.runtime.broker_readiness_framework import (
    broker_readiness_payload,
    build_broker_readiness_snapshot,
)
from backend.runtime.live_execution_authority import evaluate_live_execution_authority
from backend.runtime.live_readiness_state_machine import evaluate_live_readiness_state


def _ready_payload(broker_name: str) -> dict[str, object]:
    readiness = broker_readiness_payload(
        build_broker_readiness_snapshot(
            {
                "broker_name": broker_name,
                "broker_type": "CRYPTO" if broker_name == "COINBASE" else "FX",
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
                "execution_enabled": True,
                "last_successful_sync": "2026-07-04T12:00:00+00:00",
                "account_balance": 100.0,
                "equity": 100.0,
                "buying_power": 90.0,
            }
        )
    )
    return {
        "broker_readiness": readiness,
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


def test_phase154a_broker_readiness_contract_is_identical_for_coinbase_and_oanda() -> None:
    coinbase = broker_readiness_payload(build_broker_readiness_snapshot({"broker_name": "COINBASE", "broker_type": "CRYPTO", "credential_status": "PRESENT"}))
    oanda = broker_readiness_payload(build_broker_readiness_snapshot({"broker_name": "OANDA", "broker_type": "FX", "credential_status": "PRESENT"}))

    assert set(coinbase) == set(oanda)
    assert coinbase["broker_name"] == "COINBASE"
    assert oanda["broker_name"] == "OANDA"
    assert coinbase["broker_type"] == "CRYPTO"
    assert oanda["broker_type"] == "FX"
    for key in (
        "infrastructure_health",
        "credentials_health",
        "authentication_health",
        "connection_health",
        "market_data_health",
        "account_data_health",
    ):
        assert key in coinbase
        assert key in oanda
    assert coinbase["execution_allowed"] is False
    assert oanda["execution_allowed"] is False


def test_phase154a_live_execution_authority_uses_framework_not_broker_name() -> None:
    coinbase_decision = evaluate_live_execution_authority(_ready_payload("COINBASE"))
    oanda_decision = evaluate_live_execution_authority(_ready_payload("OANDA"))

    assert coinbase_decision.execution_authority is True
    assert oanda_decision.execution_authority is True
    assert coinbase_decision.condition_status == oanda_decision.condition_status


def test_phase154a_readiness_state_uses_framework_for_any_broker() -> None:
    coinbase_state = evaluate_live_readiness_state({"broker_readiness": _ready_payload("COINBASE")["broker_readiness"]})
    oanda_state = evaluate_live_readiness_state({"broker_readiness": _ready_payload("OANDA")["broker_readiness"]})

    assert coinbase_state.readiness_state == "MARKET_DATA_READY"
    assert oanda_state.readiness_state == "MARKET_DATA_READY"
    assert coinbase_state.as_dict()["startup_diagnostics"]["broker_ready"] is True
    assert oanda_state.as_dict()["startup_diagnostics"]["broker_ready"] is True
