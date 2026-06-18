import pytest
from unittest.mock import patch
from dashboard.mobile.mobile_app import execute_mobile_trade_ticket
from engine.risk.broker_margin_contract import BrokerMarginSnapshot

def test_mobile_risk_path_unmocked_fails_closed():
    user_ctx = {"role": "SUPER_USER", "user_id": "test_1", "submit_trade": True}
    form = {
        "broker": "COINBASE",
        "asset_class": "CRYPTO",
        "symbol": "BTC-USD",
        "side": "BUY",
        "amount": "100.0",
        "confirm": "MOBILE LIVE"
    }

    with patch("dashboard.mobile.mobile_app.load_mobile_controls") as mock_controls:
        mock_controls.return_value = {
            "mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED",
            "global_live_order_kill_switch": False
        }
        with patch("dashboard.mobile.mobile_app.SessionRuntimeService") as MockSession:
            instance = MockSession.return_value
            instance.get_active_sessions.return_value = [{"session_id": "test_session_1"}]
            
            with patch("dashboard.mobile.mobile_app.PnlRuntimeService") as MockPnl:
                pnl_instance = MockPnl.return_value
                pnl_instance.get_latest_snapshot.return_value = {
                    "equity": 50000.0,
                    "equity_peak": 50000.0
                }
                
                with patch("engine.risk.coinbase_margin_adapter.CoinbaseMarginAdapter") as MockMargin:
                    margin_instance = MockMargin.return_value
                    margin_instance.get_margin_snapshot.return_value = BrokerMarginSnapshot(
                        broker_name="COINBASE",
                        account_id="SIMULATED",
                        margin_source="SIMULATED",
                        required_margin=1000.0,
                        available_margin=49000.0,
                        free_margin=48000.0,
                        margin_utilization_pct=0.02,
                        timestamp="2026-06-16T00:00:00Z"
                    )
                    
                    # Execution
                    result = execute_mobile_trade_ticket(user_ctx, form)
                    
                    # Verification
                    assert result["ok"] is False
                    assert result["status"] in ("EXECUTION_GATE_REJECTED", "ORCHESTRATOR_GATE_REJECTED")
