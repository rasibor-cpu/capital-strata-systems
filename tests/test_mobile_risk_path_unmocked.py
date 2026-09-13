from unittest.mock import patch

from dashboard.mobile.mobile_app import execute_mobile_trade_ticket


def test_mobile_live_request_fails_closed_before_risk_or_execution():
    user_ctx = {
        "role": "SUPER_USER",
        "user_id": "test_1",
        "submit_trade": True,
    }
    form = {
        "broker": "COINBASE",
        "asset_class": "CRYPTO",
        "symbol": "BTC-USD",
        "side": "BUY",
        "amount": "100.0",
        "confirm": "MOBILE LIVE",
    }

    with patch(
        "dashboard.mobile.mobile_app.load_mobile_controls"
    ) as mock_controls:
        mock_controls.return_value = {
            "mobile_trading_mode": "MOBILE_LIVE_READ_ONLY",
            "runtime_mode": "live",
            "orders_enabled": False,
            "engine_mode": "SAFE",
            "live_order_kill_switch": False,
        }

        result = execute_mobile_trade_ticket(user_ctx, form)

    assert result["ok"] is False
    assert result["status"] == "MOBILE_LIVE_EXECUTION_NOT_AUTHORIZED"
    assert result["broker_response"]["live_order_sent"] is False
    assert result["broker_response"]["read_only"] is True
