from __future__ import annotations

import json
from pathlib import Path

from backend.runtime.live_readiness_state_machine import (
    LIVE_READINESS_STATES,
    evaluate_live_readiness_state,
    publish_live_readiness_state,
)


def test_phase153h_state_machine_progresses_only_from_explicit_evidence() -> None:
    base = {
        "selected_broker": "COINBASE",
        "broker_mode": "live",
        "execution_scope": "LIVE READ-ONLY VALIDATION",
        "broker_execution_armed": False,
        "can_live_execute": False,
        "live_micro_pilot_state": "DISARMED",
        "broker_guard": "REJECT_BEFORE_BROKER",
    }

    assert LIVE_READINESS_STATES[0] == "UNCONFIGURED"
    assert evaluate_live_readiness_state(base).readiness_state == "UNCONFIGURED"
    assert evaluate_live_readiness_state({**base, "credential_status": "PRESENT"}).readiness_state == "CREDENTIALS_PRESENT"
    assert evaluate_live_readiness_state({**base, "credential_status": "PRESENT", "broker_authenticated": True}).readiness_state == "AUTHENTICATED"
    assert evaluate_live_readiness_state({**base, "credential_status": "PRESENT", "broker_authenticated": True, "broker_connected": True}).readiness_state == "CONNECTED"
    assert evaluate_live_readiness_state(
        {**base, "credential_status": "PRESENT", "broker_authenticated": True, "broker_connected": True, "account_equity": 20.0}
    ).readiness_state == "ACCOUNT_DATA_READY"
    assert evaluate_live_readiness_state(
        {
            **base,
            "credential_status": "PRESENT",
            "broker_authenticated": True,
            "broker_connected": True,
            "account_equity": 20.0,
            "products_loaded": 1,
            "market_data_status": "OK",
        }
    ).readiness_state == "READ_ONLY_READY"


def test_phase153h_read_only_ready_requires_execution_disabled_and_pilot_disarmed() -> None:
    ready = {
        "selected_broker": "COINBASE",
        "broker_mode": "live",
        "credential_status": "PRESENT",
        "broker_authenticated": True,
        "broker_connected": True,
        "account_equity": 20.0,
        "products_loaded": 1,
        "market_data_status": "OK",
        "broker_execution_armed": False,
        "can_live_execute": False,
        "live_micro_pilot_state": "DISARMED",
        "broker_guard": "REJECT_BEFORE_BROKER",
    }
    armed = {**ready, "broker_execution_armed": True, "can_live_execute": True}

    ready_state = evaluate_live_readiness_state(ready).as_dict()
    armed_state = evaluate_live_readiness_state(armed).as_dict()

    assert ready_state["readiness_state"] == "READ_ONLY_READY"
    assert ready_state["go_no_go"] == "GO"
    assert armed_state["readiness_state"] == "MARKET_DATA_READY"
    assert armed_state["go_no_go"] == "NO GO"


def test_phase153h_state_machine_publishes_canonical_artifact(tmp_path: Path) -> None:
    path = tmp_path / "live_readiness_state.json"
    published = publish_live_readiness_state(
        path,
        {
            "selected_broker": "COINBASE",
            "broker_mode": "live",
            "credential_status": "PRESENT",
            "broker_authenticated": True,
            "broker_connected": True,
            "account_equity": 20.0,
            "products_loaded": 2,
            "market_data_status": "PASS",
            "broker_execution_armed": False,
            "can_live_execute": False,
            "live_micro_pilot_state": "DISARMED",
            "broker_guard": "REJECT_BEFORE_BROKER",
            "live_validated": True,
        },
    )
    loaded = json.loads(path.read_text(encoding="utf-8"))

    assert published["readiness_state"] == "LIVE_VALIDATED"
    assert loaded["startup_diagnostics"]["broker"] == "COINBASE"
    assert loaded["startup_diagnostics"]["execution_enabled"] is False
    assert any(item["label"] == "Orders blocked" and item["passed"] for item in loaded["readiness_checklist"])
