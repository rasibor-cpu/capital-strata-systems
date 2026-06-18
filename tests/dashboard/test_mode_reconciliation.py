from __future__ import annotations

import dashboard.mobile.mobile_app as mobile_app
from dashboard.runtime.dashboard_hydration_coordinator import (
    DashboardHydrationCoordinator,
)
from dashboard.runtime.frontend_contract import build_frontend_payload
from dashboard.runtime.runtime_smoke_test import build_smoke_payloads


def _state(*, session_mode: str, broker_mode: str):
    payloads = build_smoke_payloads()
    payloads["session_payload"] = {
        **payloads["session_payload"],
        "live_or_paper": session_mode,
    }
    payloads["broker_payload"] = {
        "selected_broker": "IBKR",
        "broker_mode": broker_mode,
        "connected": True,
        "live_trading_enabled": broker_mode == "live",
    }
    return DashboardHydrationCoordinator().hydrate(**payloads)


def test_dashboard_and_frontend_resolve_live_only_when_session_and_broker_agree() -> None:
    state = _state(session_mode="live", broker_mode="live")
    frontend = build_frontend_payload(state)

    assert state.resolved_mode() == "live"
    assert state.to_dict()["resolved_mode"] == "live"
    assert frontend["resolved_mode"] == "live"
    assert frontend["session"]["resolved_mode"] == "live"
    assert frontend["sections"]["broker"]["broker_mode"] == "live"


def test_dashboard_and_frontend_fall_back_to_paper_on_mode_disagreement() -> None:
    for session_mode, broker_mode in (
        ("live", "paper"),
        ("paper", "live"),
        ("simulated", "live"),
        ("", "live"),
    ):
        state = _state(session_mode=session_mode, broker_mode=broker_mode)
        frontend = build_frontend_payload(state)

        assert state.resolved_mode() == "paper"
        assert state.to_dict()["resolved_mode"] == "paper"
        assert frontend["resolved_mode"] == "paper"
        assert frontend["session"]["resolved_mode"] == "paper"


def test_mobile_controls_report_runtime_mode_and_order_gate_consistently(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    controls = mobile_app.save_mobile_controls(
        {
            "mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED",
            "engine_mode": "BALANCED",
            "live_order_kill_switch": False,
        }
    )
    status = mobile_app._system_status(
        {
            "user_id": "00017",
            "display_name": "CSS Trader",
            "role": "TRADER",
        }
    )

    assert controls["orders_enabled"] is True
    assert controls["engine_mode"] == "BALANCED"
    assert status["runtime_mode"] == "live"
    assert status["system_live"] is True
    assert status["orders_enabled"] is True
    assert status["engine_mode"] == "BALANCED"
    assert status["broker_live_gate"] == "READY"


def test_mobile_controls_normalize_unknown_modes_to_paper(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")

    controls = mobile_app.save_mobile_controls(
        {
            "runtime_mode": "unsupported",
            "orders_enabled": True,
            "engine_mode": "unsupported",
        }
    )
    status = mobile_app._system_status({"role": "TRADER"})

    assert controls["runtime_mode"] == "paper"
    assert controls["engine_mode"] == "SAFE"
    assert status["runtime_mode"] == "paper"
    assert status["system_live"] is False
    assert status["engine_mode"] == "SAFE"
