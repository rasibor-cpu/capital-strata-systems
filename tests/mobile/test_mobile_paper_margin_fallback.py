import pytest
from unittest.mock import patch, MagicMock
from dashboard.mobile.mobile_app import execute_mobile_trade_ticket

def test_paper_mobile_trade_uses_synthetic_margin_fallback():
    # Arrange
    user_ctx = {"role": "TRADER", "user_id": "U1"}
    form = {
        "broker": "CSS_PAPER",
        "asset_class": "FX",
        "symbol": "EUR_USD",
        "side": "BUY",
        "qty": "1000",
        "amount": "1000.00"
    }
    
    with patch("dashboard.mobile.mobile_app._can_submit_trade", return_value=True), \
         patch("dashboard.mobile.mobile_app.load_mobile_controls", return_value={"mobile_trading_mode": "MOBILE_PAPER_TRADING"}), \
         patch("dashboard.mobile.mobile_app.SessionRuntimeService") as mock_session_svc, \
         patch("dashboard.mobile.mobile_app.PnlRuntimeService") as mock_pnl_svc, \
         patch("backend.intelligence.trade_decision_orchestrator.TradeDecisionOrchestrator") as mock_orchestrator, \
         patch("engine.execution.execution_gate.ExecutionGate") as mock_exec_gate, \
         patch("backend.app.persistence.services.trade_runtime_service.TradeRuntimeService") as mock_trade_svc:
        
        # Mock Session and Pnl
        mock_session_svc.return_value.get_active_sessions.return_value = [{"session_id": "session1"}]
        mock_pnl_svc.return_value.get_latest_snapshot.return_value = {"equity": 10000.0, "equity_peak": 10000.0}
        
        # Mock Orchestrator
        mock_orch_inst = mock_orchestrator.return_value
        mock_orch_inst.evaluate_trade.return_value = {"filters": {"governance_approved": True}}
        mock_orch_inst.session_id = "session1"
        
        # Mock Execution Gate
        mock_exec_gate_inst = mock_exec_gate.return_value
        mock_exec_gate_inst.evaluate_trade.return_value = {"decision": {"final": "ALLOW"}}
        
        # Act
        result = execute_mobile_trade_ticket(user_ctx, form)
        
        # Assert
        assert result["ok"] is True
        assert result["status"] == "MOBILE_ORDER_APPROVED"
        assert result["broker_response"]["live_order_sent"] is False
        
        # Verify execution gate was called with the fallback margin snapshot
        call_kwargs = mock_exec_gate_inst.evaluate_trade.call_args[1]
        fallback_snapshot = call_kwargs["margin_snapshot"]
        assert fallback_snapshot is not None
        assert fallback_snapshot.margin_source == "SIMULATED"
        assert fallback_snapshot.broker_mode == "PAPER"
        assert fallback_snapshot.available_margin == 10000.00
        assert fallback_snapshot.required_margin == 0.00
        assert fallback_snapshot.utilization_pct == 0.00
        assert fallback_snapshot.trade_gate_allowed is True
        assert fallback_snapshot.reason == "PAPER_SIMULATED_MARGIN_FALLBACK"


def test_live_mobile_trade_blocks_on_missing_margin():
    # Arrange
    user_ctx = {"role": "SUPER_USER", "user_id": "U1"}
    form = {
        "broker": "OANDA",
        "asset_class": "FX",
        "symbol": "EUR_USD",
        "side": "BUY",
        "qty": "1000",
        "amount": "1000.00",
        "confirm": "MOBILE LIVE"
    }
    
    with patch("dashboard.mobile.mobile_app._can_submit_trade", return_value=True), \
         patch("dashboard.mobile.mobile_app.load_mobile_controls", return_value={"mobile_trading_mode": "MOBILE_LIVE_TRADING_ARMED"}), \
         patch("dashboard.mobile.mobile_app.evaluate_live_order_kill_switch", return_value=MagicMock(blocked=False)), \
         patch("dashboard.mobile.mobile_app.SessionRuntimeService") as mock_session_svc, \
         patch("dashboard.mobile.mobile_app.PnlRuntimeService") as mock_pnl_svc, \
         patch("engine.risk.oanda_margin_adapter.OandaMarginAdapter", side_effect=Exception("API Down")):
         
        mock_session_svc.return_value.get_active_sessions.return_value = [{"session_id": "session1"}]
        mock_pnl_svc.return_value.get_latest_snapshot.return_value = {"equity": 10000.0, "equity_peak": 10000.0}
        
        # Act
        result = execute_mobile_trade_ticket(user_ctx, form)
        
        # Assert
        assert result["ok"] is False
        assert result["status"] == "MARGIN_SNAPSHOT_UNAVAILABLE"
        assert "error" in result["broker_response"]

