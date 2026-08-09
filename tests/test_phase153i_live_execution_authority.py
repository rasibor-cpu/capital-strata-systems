from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.runtime.live_execution_authority import evaluate_live_execution_authority
from backend.runtime.startup_summary import build_live_startup_summary, format_live_startup_summary
from backend.runtime.startup_state_machine import run_startup_state_machine
from dashboard.runtime.frontend_contract import build_frontend_payload
import launcher.css_mobile_launcher as launcher


def _valid_live_authority_lease(
    broker: str,
    environment: str = "LIVE",
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    return {
        "lease_id": f"phase196-test-{broker.lower()}",
        "issued_at": (now - timedelta(seconds=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(seconds=299)).isoformat().replace("+00:00", "Z"),
        "broker": broker,
        "environment": environment,
        "action": "LIVE_EXECUTE",
        "scope": "LIVE_EXECUTION",
        "consumed": False,
        "revoked": False,
        "generation": 1,
    }

def _all_pass_evidence() -> dict[str, object]:
    return {
        "operator_requested_live": True,
        "selected_broker": "OANDA",
        "broker_mode": "LIVE",
        "live_authority_lease": _valid_live_authority_lease("OANDA"),
        "credential_status": "PRESENT",
        "broker_authenticated": True,
        "broker_connected": True,
        "account_equity": 20.0,
        "products_loaded": 1,
        "market_data_status": "OK",
        "broker_execution_enabled": True,
        "live_micro_pilot_state": "ARMED",
        "capital_governor": "PASS",
        "unified_trade_gate": "PASS",
        "margin_gate": "PASS",
        "anti_bleed_guard": "PASS",
        "rbac": "PASS",
        "kill_switch": "CLEAR",
        "go_no_go": "GO",
    }


def test_phase153i_arm_live_is_operator_intent_not_execution_authority() -> None:
    decision = evaluate_live_execution_authority(
        {
            "operator_requested_live": True,
        "selected_broker": "OANDA",
        "broker_mode": "LIVE",
        "live_authority_lease": _valid_live_authority_lease("OANDA"),
            "credential_status": "MISSING",
            "broker_authenticated": False,
            "broker_connected": False,
            "broker_execution_enabled": False,
            "live_micro_pilot_state": "DISARMED",
            "go_no_go": "NO GO",
        }
    )

    assert decision.operator_requested_live is True
    assert decision.execution_authority is False
    assert decision.can_live_execute is False
    assert decision.authority_reason == "Credentials Missing"
    assert "credentials_present" in decision.failed_conditions


def test_phase153i_authority_requires_every_condition() -> None:
    missing_pilot = {**_all_pass_evidence(), "live_micro_pilot_state": "DISARMED"}
    all_pass = _all_pass_evidence()

    blocked = evaluate_live_execution_authority(missing_pilot)
    granted = evaluate_live_execution_authority(all_pass)

    assert blocked.execution_authority is False
    assert blocked.authority_reason == "Pilot Disarmed"
    assert granted.execution_authority is True
    assert granted.can_live_execute is True
    assert granted.authority_reason == "Authority Granted"


def test_phase153i_startup_summary_reconciles_operator_intent_with_authority() -> None:
    summary = build_live_startup_summary(
        {
            "selected_broker": "COINBASE",
            "broker_mode": "live",
            "operator_requested_live": True,
        "selected_broker": "OANDA",
        "broker_mode": "LIVE",
        "live_authority_lease": _valid_live_authority_lease("OANDA"),
            "broker_execution_armed": False,
            "can_live_execute": True,
        },
        broker_status={
            "credential_status": "MISSING",
            "broker_authenticated": False,
            "broker_connected": False,
            "go_no_go": "NO GO",
        },
        pilot_status={"pilot_state": "DISARMED"},
    )
    text = "\n".join(format_live_startup_summary(summary))

    assert "Operator Requested Live: YES" in text
    assert "Execution Authority: NO" in text
    assert "Can Live Execute: NO" in text
    assert "Authority Reason: Credentials Missing" in text
    assert "Broker Execution: ARMED" not in text
    assert summary["execution_authority"] is False
    assert summary["can_live_execute"] is False


def test_phase153i_startup_state_machine_arm_live_does_not_grant_authority() -> None:
    inputs = iter(["2", "LIVE", "2", "2", "LIVE", "2", "ARM LIVE", "1", "1", "Y"])
    output: list[str] = []
    result = run_startup_state_machine(
        input_func=lambda _prompt: next(inputs),
        output_func=output.append,
        flush_func=lambda: None,
        role_profile={"can_arm_broker": True, "allowed_engine_modes": ["SAFE"]},
        pilot_status={"pilot_state": "DISARMED", "canonical_live_pilot_limit_cad": "20.00"},
    )
    text = "\n".join(output)

    assert result.state.operator_requested_live is True
    assert result.state.broker_execution_armed is False
    assert result.state.execution_authority is False
    assert result.state.can_live_execute is False
    assert "Operator Requested Live: YES" in text
    assert "Execution Authority: NO" in text
    assert "Broker Execution: ARMED" not in text


def test_phase153i_dashboard_and_launcher_expose_authority_fields() -> None:
    payload = build_frontend_payload(
        {
            "broker_summary": {
                "selected_broker": "COINBASE",
                "broker_mode": "live",
                "operator_requested_live": True,
        "selected_broker": "OANDA",
        "broker_mode": "LIVE",
        "live_authority_lease": _valid_live_authority_lease("OANDA"),
                "execution_authority": False,
                "authority_reason": "Credentials Missing",
                "live_authority_state": "BLOCKED",
                "can_live_execute": False,
                "broker_execution_status": "DISABLED",
            }
        }
    )
    broker = payload["sections"]["broker"]

    assert broker["operator_requested_live"] is True
    assert broker["execution_authority"] is False
    assert broker["authority_reason"] == "Credentials Missing"
    assert broker["live_authority_state"] == "BLOCKED"
    assert broker["can_live_execute"] is False


def test_phase153i_launcher_authority_endpoint_is_read_only(monkeypatch) -> None:
    monkeypatch.setattr(
        launcher,
        "get_launcher_broker_read_only_status_feed",
        lambda: {
            "operator_requested_live": True,
        "selected_broker": "OANDA",
        "broker_mode": "LIVE",
        "live_authority_lease": _valid_live_authority_lease("OANDA"),
            "execution_authority": False,
            "authority_reason": "Credentials Missing",
            "live_authority_state": "BLOCKED",
            "can_live_execute": False,
        },
    )
    response = TestClient(launcher.app).get("/api/v1/live-execution-authority")

    assert response.status_code == 200
    body = response.json()
    assert body["execution_allowed"] is False
    assert body["data"]["operator_requested_live"] is True
    assert body["data"]["execution_authority"] is False
    assert body["data"]["can_live_execute"] is False
