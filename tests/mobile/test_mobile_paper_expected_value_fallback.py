import pytest
from unittest.mock import patch, MagicMock
from dashboard.mobile.mobile_app import execute_mobile_trade_ticket

def test_paper_mobile_trade_receives_expected_value_fallback():
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
        
        # Verify orchestrator was called with gate-aligned paper defaults (SAFE → 0.65)
        from backend.governance.css_unified_trade_gate import ENGINE_MODE_PROBABILITY_THRESHOLD

        call_kwargs = mock_orch_inst.evaluate_trade.call_args[0][0]
        safe_threshold = float(ENGINE_MODE_PROBABILITY_THRESHOLD["SAFE"])
        assert call_kwargs["expected_value"] == 1.0
        assert call_kwargs["cost"] == 0.0
        assert call_kwargs["signal_score"] == 1.0
        assert call_kwargs["probability"] == safe_threshold
        assert call_kwargs["confidence"] == safe_threshold
        assert call_kwargs["validation_source"] == "MOBILE_PAPER_TEST_DEFAULTS"

        # Phase 183J: paper path supplies finite ExecutionGate anti-bleed inputs
        gate_kwargs = mock_exec_gate_inst.evaluate_trade.call_args.kwargs
        assert gate_kwargs["expected_move_bps"] == 50.0
        assert gate_kwargs["fee_bps"] == 1.0
        assert gate_kwargs["spread_bps"] == 1.0
        assert gate_kwargs["slippage_bps"] == 1.0
        assert gate_kwargs["regime_persistence"] == 0.5
        assert gate_kwargs["volatility_state"] == "MEDIUM"
        assert gate_kwargs["regime_state"] == "NORMAL"
        assert gate_kwargs["broker_mode"] == "paper"

def test_live_mobile_trade_does_not_receive_expected_value_fallback():
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
         patch("engine.risk.oanda_margin_adapter.OandaMarginAdapter") as mock_margin_adapter, \
         patch("backend.intelligence.trade_decision_orchestrator.TradeDecisionOrchestrator") as mock_orchestrator, \
         patch("engine.execution.execution_gate.ExecutionGate") as mock_exec_gate, \
         patch("backend.app.persistence.services.trade_runtime_service.TradeRuntimeService") as mock_trade_svc:
         
        mock_session_svc.return_value.get_active_sessions.return_value = [{"session_id": "session1"}]
        mock_pnl_svc.return_value.get_latest_snapshot.return_value = {"equity": 10000.0, "equity_peak": 10000.0}
        
        mock_margin_adapter_inst = mock_margin_adapter.return_value
        mock_margin_adapter_inst.get_margin_snapshot.return_value = {"buying_power": 10000.0, "margin_ratio": 0.0, "margin_state": "NORMAL"}
        
        # Mock Orchestrator to block without expected value
        mock_orch_inst = mock_orchestrator.return_value
        mock_orch_inst.evaluate_trade.return_value = {"filters": {"governance_approved": False, "governance_reason": "negative or zero expected value"}}
        mock_orch_inst.session_id = "session1"
        
        # Act
        result = execute_mobile_trade_ticket(user_ctx, form)
        
        # Assert
        assert result["ok"] is False
        assert result["status"] == "ORCHESTRATOR_GATE_REJECTED"
        assert result["broker_response"]["reason"] == "negative or zero expected value"
        
        # Verify orchestrator was called without fallback
        call_kwargs = mock_orch_inst.evaluate_trade.call_args[0][0]
        assert call_kwargs["expected_value"] is None
