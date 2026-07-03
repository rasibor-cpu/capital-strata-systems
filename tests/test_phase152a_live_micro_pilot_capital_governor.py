from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

import dashboard.mobile.mobile_app as mobile_app
from backend.runtime.live_micro_pilot_governor import (
    LiveMicroPilotAuthorizationError,
    LiveMicroPilotConfig,
    LiveMicroPilotConfigurationError,
    LiveMicroPilotGovernor,
)
from dashboard.runtime.api_bridge import create_app
from dashboard.runtime.frontend_contract import build_frontend_payload
from launcher.css_mobile_launcher import get_launcher_live_micro_pilot_feed


SUPER_USER = {"user_id": "00000", "display_name": "CSS Administrator", "role": "SUPER_USER"}
TRADER = {"user_id": "00017", "display_name": "CSS Trader", "role": "TRADER"}


def _governor(tmp_path, monkeypatch) -> LiveMicroPilotGovernor:
    config = tmp_path / "pilot_config.json"
    state = tmp_path / "pilot_state.json"
    audit = tmp_path / "pilot_audit.jsonl"
    monkeypatch.setenv("CSS_LIVE_MICRO_PILOT_CONFIG", str(config))
    monkeypatch.setenv("CSS_LIVE_MICRO_PILOT_STATE", str(state))
    monkeypatch.setenv("CSS_LIVE_MICRO_PILOT_AUDIT", str(audit))
    return LiveMicroPilotGovernor(config_path=config, state_path=state, audit_path=audit)


def _configured_and_armed(tmp_path, monkeypatch) -> LiveMicroPilotGovernor:
    governor = _governor(tmp_path, monkeypatch)
    governor.write_config({"pilot_enabled": True}, user_ctx=SUPER_USER, confirmation_word="EXECUTE")
    governor.arm(user_ctx=SUPER_USER, confirmation_word="EXECUTE")
    return governor


def _live_order(amount: str = "1.00", *, symbol: str = "BTC-USD", side: str = "BUY") -> dict[str, str]:
    return {
        "broker": "COINBASE",
        "broker_mode": "live",
        "mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED",
        "symbol": symbol,
        "side": side,
        "notional": amount,
    }


def test_phase152a_defaults_are_safe_and_disabled() -> None:
    config = LiveMicroPilotGovernor.default_config()

    assert config.pilot_enabled is False
    assert config.currency == "CAD"
    assert str(config.max_live_test_capital) == "20.00"
    assert str(config.max_position_size) == "20.00"
    assert config.max_concurrent_positions == 1
    assert config.max_orders_per_session == 10
    assert str(config.daily_loss_limit) == "2.00"
    assert str(config.session_loss_limit) == "4.00"
    assert config.allow_pyramiding is False
    assert config.allow_averaging_down is False
    assert config.require_manual_live_arming is True
    assert config.require_explicit_confirmation_word == "EXECUTE"
    assert config.auto_disarm_on_limit_breach is True
    assert config.fail_closed_if_config_missing is True


def test_phase152a_missing_config_fails_closed_for_live(tmp_path, monkeypatch) -> None:
    governor = _governor(tmp_path, monkeypatch)

    decision = governor.evaluate_order(_live_order("1.00"))

    assert decision.approved is False
    assert decision.reason == "live_micro_pilot_config_missing"
    assert decision.status["broker_submission_guard"] == "REJECT_BEFORE_BROKER"


@pytest.mark.parametrize(
    ("order", "positions", "reason"),
    [
        (_live_order("21.00"), [], "max_position_size_breached"),
        (_live_order("11.00"), [{"symbol": "ETH-USD", "side": "BUY", "notional": "10.00"}], "max_live_test_capital_breached"),
        (_live_order("1.00", symbol="ETH-USD"), [{"symbol": "BTC-USD", "side": "BUY", "notional": "1.00"}], "max_concurrent_positions_breached"),
        (_live_order("1.00"), [{"symbol": "BTC-USD", "side": "BUY", "notional": "1.00"}], "pyramiding_blocked"),
        (_live_order("1.00"), [{"symbol": "BTC-USD", "side": "BUY", "notional": "1.00", "unrealized_pnl": "-0.25"}], "averaging_down_blocked"),
    ],
)
def test_phase152a_live_limits_reject_before_broker(tmp_path, monkeypatch, order, positions, reason) -> None:
    governor = _configured_and_armed(tmp_path, monkeypatch)

    decision = governor.evaluate_order(order, open_positions=positions)

    assert decision.approved is False
    assert decision.reason == reason
    assert decision.status["pilot_armed"] is False


def test_phase152a_order_and_loss_limits_auto_disarm(tmp_path, monkeypatch) -> None:
    governor = _configured_and_armed(tmp_path, monkeypatch)
    state = {"pilot_armed": True, "pilot_state": "ARMED", "orders_used_this_session": 10, "open_positions": []}

    order_decision = governor.evaluate_order(_live_order("1.00"), state=state)
    daily_loss_decision = governor.evaluate_order(_live_order("1.00"), state={**state, "orders_used_this_session": 0}, daily_pnl="-2.00")
    session_loss_decision = governor.evaluate_order(_live_order("1.00"), state={**state, "orders_used_this_session": 0}, session_pnl="-4.00")

    assert order_decision.reason == "max_orders_per_session_breached"
    assert daily_loss_decision.reason == "daily_loss_limit_breached"
    assert session_loss_decision.reason == "session_loss_limit_breached"
    assert session_loss_decision.status["pilot_state"] == "LIMIT_BREACHED"


def test_phase152a_super_user_only_controls_and_confirmation(tmp_path, monkeypatch) -> None:
    governor = _governor(tmp_path, monkeypatch)

    with pytest.raises(LiveMicroPilotAuthorizationError):
        governor.write_config({"pilot_enabled": True}, user_ctx=TRADER, confirmation_word="EXECUTE")
    with pytest.raises(LiveMicroPilotAuthorizationError):
        governor.write_config({"pilot_enabled": True}, user_ctx=SUPER_USER, confirmation_word="GO")

    status = governor.write_config({"pilot_enabled": True}, user_ctx=SUPER_USER, confirmation_word="EXECUTE")
    assert status["pilot_enabled"] is True


def test_phase152a_unsafe_config_cannot_raise_limits() -> None:
    with pytest.raises(LiveMicroPilotConfigurationError):
        LiveMicroPilotConfig.from_mapping({"pilot_enabled": True, "max_live_test_capital": "21.00"})
    with pytest.raises(LiveMicroPilotConfigurationError):
        LiveMicroPilotConfig.from_mapping({"pilot_enabled": True, "allow_pyramiding": "true"})
    with pytest.raises(LiveMicroPilotConfigurationError):
        LiveMicroPilotConfig.from_mapping({"pilot_enabled": True, "currency": "USD"})


def test_phase152a_paper_order_is_unchanged_by_pilot(tmp_path, monkeypatch) -> None:
    governor = _governor(tmp_path, monkeypatch)

    decision = governor.evaluate_order({"broker": "CSS_PAPER", "broker_mode": "paper", "symbol": "BTC-USD", "notional": "1000.00"})

    assert decision.approved is True
    assert decision.reason == "not_live_request"


def test_phase152a_mobile_live_pilot_rejects_before_trade_runtime_service(tmp_path, monkeypatch) -> None:
    _configured_and_armed(tmp_path, monkeypatch)
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls({"mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED"})

    with patch("dashboard.mobile.mobile_app.evaluate_live_order_kill_switch", return_value=MagicMock(blocked=False, reason="", source="test")), \
        patch("dashboard.mobile.mobile_app.SessionRuntimeService") as mock_session_svc, \
        patch("dashboard.mobile.mobile_app.PnlRuntimeService") as mock_pnl_svc, \
        patch("engine.risk.coinbase_margin_adapter.CoinbaseMarginAdapter") as mock_margin_adapter, \
        patch("backend.intelligence.trade_decision_orchestrator.TradeDecisionOrchestrator") as mock_orchestrator, \
        patch("engine.execution.execution_gate.ExecutionGate") as mock_exec_gate, \
        patch("backend.app.persistence.services.trade_runtime_service.TradeRuntimeService") as mock_trade_service:
        mock_session_svc.return_value.get_active_sessions.return_value = [{"session_id": "session1"}]
        mock_pnl_svc.return_value.get_latest_snapshot.return_value = {"equity": 10000.0, "equity_peak": 10000.0}
        mock_margin_adapter.return_value.get_margin_snapshot.return_value = object()
        mock_orchestrator.return_value.evaluate_trade.return_value = {"filters": {"governance_approved": True}}
        mock_orchestrator.return_value.session_id = "session1"
        mock_exec_gate.return_value.evaluate_trade.return_value = {"decision": {"final": "ALLOW"}, "reason": "approved"}

        result = mobile_app.execute_mobile_trade_ticket(
            SUPER_USER,
            {
                "broker": "COINBASE",
                "asset_class": "CRYPTO",
                "symbol": "BTC-USD",
                "side": "BUY",
                "amount": "21.00",
                "qty": "1",
                "confirm": "MOBILE LIVE",
            },
        )

    assert result["ok"] is False
    assert result["status"] == "LIVE_MICRO_PILOT_REJECTED"
    assert result["broker_response"]["live_order_sent"] is False
    mock_trade_service.return_value.open_trade.assert_not_called()


def test_phase152a_existing_unified_execution_gate_still_blocks_live(tmp_path, monkeypatch) -> None:
    _configured_and_armed(tmp_path, monkeypatch)
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls({"mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED"})

    with patch("dashboard.mobile.mobile_app.evaluate_live_order_kill_switch", return_value=MagicMock(blocked=False, reason="", source="test")), \
        patch("dashboard.mobile.mobile_app.SessionRuntimeService") as mock_session_svc, \
        patch("dashboard.mobile.mobile_app.PnlRuntimeService") as mock_pnl_svc, \
        patch("engine.risk.coinbase_margin_adapter.CoinbaseMarginAdapter") as mock_margin_adapter, \
        patch("backend.intelligence.trade_decision_orchestrator.TradeDecisionOrchestrator") as mock_orchestrator, \
        patch("engine.execution.execution_gate.ExecutionGate") as mock_exec_gate:
        mock_session_svc.return_value.get_active_sessions.return_value = [{"session_id": "session1"}]
        mock_pnl_svc.return_value.get_latest_snapshot.return_value = {"equity": 10000.0, "equity_peak": 10000.0}
        mock_margin_adapter.return_value.get_margin_snapshot.return_value = object()
        mock_orchestrator.return_value.evaluate_trade.return_value = {"filters": {"governance_approved": True}}
        mock_exec_gate.return_value.evaluate_trade.return_value = {"decision": {"final": "BLOCK"}, "reason": "margin_trade_gate_rejected"}

        result = mobile_app.execute_mobile_trade_ticket(
            SUPER_USER,
            {
                "broker": "COINBASE",
                "asset_class": "CRYPTO",
                "symbol": "BTC-USD",
                "side": "BUY",
                "amount": "10.00",
                "qty": "1",
                "confirm": "MOBILE LIVE",
            },
        )

    assert result["ok"] is False
    assert result["status"] == "EXECUTION_GATE_REJECTED"


def test_phase152a_dashboard_mobile_and_launcher_visibility(tmp_path, monkeypatch) -> None:
    _governor(tmp_path, monkeypatch)

    payload = build_frontend_payload({})
    assert payload["sections"]["live_micro_pilot"]["section_title"] == "Live Micro-Pilot Status"

    dashboard_api = TestClient(create_app())
    response = dashboard_api.get("/api/v1/live-micro-pilot-status")
    assert response.status_code == 200
    assert response.json()["section"] == "live_micro_pilot"

    mobile_page = mobile_app._live_micro_pilot_page(TRADER, {"created": 1.0})
    assert "Live Micro-Pilot Status" in mobile_page
    assert "Broker Submission Guard" in mobile_page

    launcher_feed = get_launcher_live_micro_pilot_feed()
    assert launcher_feed["section_title"] == "Live Micro-Pilot Status"


def test_phase152a_audit_events_record_rejections_and_operator_changes(tmp_path, monkeypatch) -> None:
    governor = _configured_and_armed(tmp_path, monkeypatch)
    audit_path = tmp_path / "pilot_audit.jsonl"

    decision = governor.evaluate_order(_live_order("21.00"))
    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]

    assert decision.reason == "max_position_size_breached"
    assert any(event["event_type"] == "LIVE_MICRO_PILOT_CONFIGURED" for event in events)
    assert any(event["event_type"] == "LIVE_MICRO_PILOT_ARMED" for event in events)
    assert any(event["event_type"] == "LIVE_MICRO_PILOT_REJECTED" for event in events)
