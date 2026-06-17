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

    def mock_eval(*args, **kwargs):
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
    assert result["status"] == "ORCHESTRATOR_GATE_REJECTED"

