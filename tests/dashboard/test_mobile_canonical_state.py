from __future__ import annotations

import dashboard.mobile.mobile_app as mobile_app


USER = {
    "user_id": "00017",
    "display_name": "CSS Trader",
    "role": "TRADER",
}
SESSION = {"created": 1.0}


def test_mobile_runtime_payload_has_no_synthetic_financial_data_when_unavailable(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        mobile_app,
        "MOBILE_CONTROL_FILE",
        tmp_path / "controls.json",
    )
    mobile_app.save_mobile_controls(
        {"mobile_trading_mode": "MOBILE_READ_ONLY"}
    )
    monkeypatch.setattr(
        mobile_app.SessionRuntimeService,
        "get_active_sessions",
        lambda self: [],
    )

    payloads = mobile_app._mobile_runtime_payloads(USER, SESSION)

    assert payloads["account_payload"]["account_readiness"] == "DATA_UNAVAILABLE"
    assert "cash_balance" not in payloads["account_payload"]
    assert "total_equity" not in payloads["account_payload"]
    assert payloads["positions_payload"]["positions"] == []
    assert payloads["market_payload"]["regime_state"] == "DATA_UNAVAILABLE"
    assert payloads["broker_payload"]["live_trading_enabled"] is False
    assert payloads["execution_payload"]["execution_state"] == (
        "MOBILE_ORDERS_DISABLED"
    )


def test_mobile_runtime_payload_uses_canonical_persisted_snapshot(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        mobile_app,
        "MOBILE_CONTROL_FILE",
        tmp_path / "controls.json",
    )
    mobile_app.save_mobile_controls(
        {"mobile_trading_mode": "MOBILE_LIVE_READ_ONLY"}
    )
    monkeypatch.setattr(
        mobile_app.SessionRuntimeService,
        "get_active_sessions",
        lambda self: [
            {
                "session_id": "SESSION-1",
                "broker_name": "QUESTRADE",
                "broker_mode": "live",
            }
        ],
    )
    monkeypatch.setattr(
        mobile_app.PnlRuntimeService,
        "get_latest_snapshot",
        lambda self, session_id: {
            "equity": "1234.56",
            "available_cash": "456.78",
            "realized_pnl": "12.34",
            "unrealized_pnl": "5.67",
            "open_positions": 2,
        },
    )

    payloads = mobile_app._mobile_runtime_payloads(USER, SESSION)

    account = payloads["account_payload"]
    assert account["account_readiness"] == "CANONICAL_RUNTIME"
    assert account["broker"] == "QUESTRADE"
    assert account["total_equity"] == "1234.56"
    assert account["cash_balance"] == "456.78"
    assert account["live_trading_enabled"] is False
    assert payloads["broker_payload"]["connected"] is True
    assert payloads["execution_payload"]["execution_state"] == (
        "MOBILE_ORDERS_DISABLED"
    )
