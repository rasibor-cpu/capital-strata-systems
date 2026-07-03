from __future__ import annotations

import pytest

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


def test_mobile_live_trade_rejects_without_super_user(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls({"mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED"})

    result = mobile_app.execute_mobile_trade_ticket(
        TRADER,
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
    assert result["status"] == "MOBILE_LIVE_REQUIRES_SUPER_USER"


def test_mobile_live_trade_rejects_without_confirmation(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls({"mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED"})

    result = mobile_app.execute_mobile_trade_ticket(
        SUPER_USER,
        {
            "broker": "COINBASE",
            "asset_class": "CRYPTO",
            "symbol": "BTC-USD",
            "side": "BUY",
            "amount": "1.00",
            "qty": "1",
            "confirm": "EXECUTE",
        },
    )
    assert result["ok"] is False
    assert result["status"] == "LIVE_CONFIRMATION_REQUIRED"


def test_mobile_live_trade_routes_to_execution_gate(monkeypatch, tmp_path):
    monkeypatch.setattr(mobile_app, "MOBILE_EVENTS_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(mobile_app, "MOBILE_CONTROL_FILE", tmp_path / "controls.json")
    mobile_app.save_mobile_controls({"mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED"})
    gate_calls = []

    monkeypatch.setattr(
        mobile_app.SessionRuntimeService,
        "get_active_sessions",
        lambda self: [{"session_id": "TEST-LIVE-SESSION"}],
    )
    monkeypatch.setattr(
        mobile_app.PnlRuntimeService,
        "get_latest_snapshot",
        lambda self, session_id: {"equity": 10000.0, "equity_peak": 10000.0},
    )

    from backend.intelligence.trade_decision_orchestrator import TradeDecisionOrchestrator
    monkeypatch.setattr(
        TradeDecisionOrchestrator,
        "evaluate_trade",
        lambda self, market_data: {"filters": {"governance_approved": True}},
    )

    from engine.risk.coinbase_margin_adapter import CoinbaseMarginAdapter
    monkeypatch.setattr(
        CoinbaseMarginAdapter,
        "get_margin_snapshot",
        lambda self: object(),
    )

    def mock_eval(*args, **kwargs):
        gate_calls.append({"args": args, "kwargs": kwargs})
        return {"decision": {"final": "BLOCK"}, "reason": "margin_trade_gate_rejected"}

    from engine.execution.execution_gate import ExecutionGate
    monkeypatch.setattr(ExecutionGate, "evaluate_trade", mock_eval)

    result = mobile_app.execute_mobile_trade_ticket(
        SUPER_USER,
        {
            "broker": "COINBASE",
            "asset_class": "CRYPTO",
            "symbol": "BTC-USD",
            "side": "BUY",
            "amount": "1000.00",
            "qty": "10",
            "confirm": "MOBILE LIVE",
        },
    )
    assert result["ok"] is False
    assert result["status"] == "EXECUTION_GATE_REJECTED"
    assert len(gate_calls) == 1
    assert gate_calls[0]["kwargs"]["broker_mode"] == "live"
    assert gate_calls[0]["kwargs"]["instrument"] == "BTC-USD"

