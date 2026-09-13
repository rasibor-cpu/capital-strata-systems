from __future__ import annotations

import dashboard.mobile.mobile_app as mobile_app

TRADER = {
    "user_id": "00017",
    "display_name": "CSS Trader",
    "role": "TRADER",
}

SUPER_USER = {
    "user_id": "00000",
    "display_name": "CSS Administrator",
    "role": "SUPER_USER",
}


def test_mobile_read_only_rejects_trades(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls({"mobile_trading_mode": "MOBILE_READ_ONLY"})

    result = mobile_app.execute_mobile_trade_ticket(
        SUPER_USER,
        {
            "broker": "CSS_PAPER",
            "asset_class": "CRYPTO",
            "symbol": "BTC-USD",
            "side": "BUY",
            "amount": "1.00",
            "qty": "1",
        },
    )
    assert result["ok"] is False
    assert result["status"] == "MOBILE_ORDERS_DISABLED"


def test_legacy_live_armed_control_is_downgraded_to_live_read_only(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")

    saved = mobile_app.save_mobile_controls(
        {"mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED"}
    )
    loaded = mobile_app.load_mobile_controls()

    assert saved["mobile_trading_mode"] == "MOBILE_LIVE_READ_ONLY"
    assert loaded["mobile_trading_mode"] == "MOBILE_LIVE_READ_ONLY"
    assert loaded["runtime_mode"] == "live"
    assert loaded["orders_enabled"] is False


def test_mobile_live_read_only_rejects_execution_for_super_user(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls(
        {"mobile_trading_mode": "MOBILE_LIVE_READ_ONLY"}
    )

    result = mobile_app.execute_mobile_trade_ticket(
        SUPER_USER,
        {
            "broker": "COINBASE",
            "asset_class": "CRYPTO",
            "symbol": "BTC-USD",
            "side": "BUY",
            "amount": "1.00",
            "qty": "1",
            "confirm": "MOBILE LIVE",
        },
    )

    assert result["ok"] is False
    assert result["status"] == "MOBILE_LIVE_EXECUTION_NOT_AUTHORIZED"
    assert result["broker_response"]["live_order_sent"] is False
    assert result["broker_response"]["read_only"] is True


def test_mobile_status_never_enables_live_orders(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls(
        {"mobile_trading_mode": "MOBILE_LIVE_READ_ONLY"}
    )

    status = mobile_app._system_status(SUPER_USER)

    assert status["system_live"] is True
    assert status["broker_live_gate"] == "READ_ONLY"
    assert status["orders_enabled"] is False
    assert status["live_orders_enabled"] is False


def test_mobile_paper_trade_still_routes_to_canonical_execution_gate(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls(
        {"mobile_trading_mode": "MOBILE_PAPER_TRADING"}
    )

    from backend.app.persistence.services.session_runtime_service import (
        SessionRuntimeService,
    )
    from backend.app.persistence.services.pnl_runtime_service import PnlRuntimeService
    from backend.intelligence.trade_decision_orchestrator import (
        TradeDecisionOrchestrator,
    )
    from engine.execution.execution_gate import ExecutionGate

    monkeypatch.setattr(
        SessionRuntimeService,
        "get_active_sessions",
        lambda self: [{"session_id": "TEST-SESSION"}],
    )
    monkeypatch.setattr(
        PnlRuntimeService,
        "get_latest_snapshot",
        lambda self, session_id: {
            "equity": 10000.0,
            "equity_peak": 10000.0,
        },
    )
    monkeypatch.setattr(
        TradeDecisionOrchestrator,
        "evaluate_trade",
        lambda self, market_data: {
            "filters": {
                "governance_approved": True,
                "governance_reason": "approved_for_test",
            }
        },
    )

    def mock_eval(*args, **kwargs):
        return {
            "decision": {"final": "BLOCK"},
            "reason": "margin_trade_gate_rejected",
        }

    monkeypatch.setattr(ExecutionGate, "evaluate_trade", mock_eval)

    result = mobile_app.execute_mobile_trade_ticket(
        SUPER_USER,
        {
            "broker": "CSS_PAPER",
            "asset_class": "CRYPTO",
            "symbol": "BTC-USD",
            "side": "BUY",
            "amount": "1000.00",
            "qty": "10",
        },
    )

    assert result["ok"] is False
    assert result["status"] == "EXECUTION_GATE_REJECTED"
