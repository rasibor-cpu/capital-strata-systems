"""MW-001 / RR-001: mobile equity_peak resolution must not default missing peak to 0."""

from __future__ import annotations

from dashboard.mobile.mobile_app import _resolve_equity_peak_for_gate


def test_resolve_equity_peak_uses_explicit_positive_peak():
    assert _resolve_equity_peak_for_gate({"equity_peak": "12000.5"}, 10000.0) == 12000.5


def test_resolve_equity_peak_defaults_missing_to_equity_when_equity_positive():
    assert _resolve_equity_peak_for_gate({}, 10000.0) == 10000.0
    assert _resolve_equity_peak_for_gate({"equity_peak": None}, 10000.0) == 10000.0


def test_resolve_equity_peak_defaults_zero_peak_to_equity():
    assert _resolve_equity_peak_for_gate({"equity_peak": 0}, 10000.0) == 10000.0
    assert _resolve_equity_peak_for_gate({"equity_peak": "0.0"}, 10000.0) == 10000.0


def test_resolve_equity_peak_defaults_invalid_peak_to_equity():
    assert _resolve_equity_peak_for_gate({"equity_peak": "not-a-number"}, 8500.0) == 8500.0
    assert _resolve_equity_peak_for_gate({"equity_peak": float("nan")}, 8500.0) == 8500.0


def test_resolve_equity_peak_keeps_zero_when_equity_also_zero():
    assert _resolve_equity_peak_for_gate({"equity_peak": 0}, 0.0) == 0.0
    assert _resolve_equity_peak_for_gate({}, 0.0) == 0.0


def test_mobile_paper_ticket_resolves_missing_peak_to_equity(monkeypatch):
    """Missing equity_peak on durable snapshot must not feed 0.0 into ExecutionGate."""
    from unittest.mock import patch

    from dashboard.mobile.mobile_app import execute_mobile_trade_ticket

    user_ctx = {"role": "TRADER", "user_id": "U1"}
    form = {
        "broker": "CSS_PAPER",
        "asset_class": "FX",
        "symbol": "EUR_USD",
        "side": "BUY",
        "qty": "1000",
        "amount": "1000.00",
    }
    monkeypatch.setenv("CSS_PAPER_COLLATERAL_RATIO", "1.0")
    with patch("dashboard.mobile.mobile_app._can_submit_trade", return_value=True), \
         patch(
             "dashboard.mobile.mobile_app.load_mobile_controls",
             return_value={"mobile_trading_mode": "MOBILE_PAPER_TRADING"},
         ), \
         patch("dashboard.mobile.mobile_app.SessionRuntimeService") as mock_session_svc, \
         patch("dashboard.mobile.mobile_app.PnlRuntimeService") as mock_pnl_svc, \
         patch(
             "backend.intelligence.trade_decision_orchestrator.TradeDecisionOrchestrator"
         ) as mock_orchestrator, \
         patch("engine.execution.execution_gate.ExecutionGate") as mock_exec_gate, \
         patch(
             "backend.app.persistence.services.trade_runtime_service.TradeRuntimeService"
         ):
        mock_session_svc.return_value.get_active_sessions.return_value = [
            {"session_id": "session1"}
        ]
        # Simulate pre-RR-001 durable snapshot (no equity_peak column / key).
        mock_pnl_svc.return_value.get_latest_snapshot.return_value = {
            "equity": 10000.0,
        }
        mock_orch_inst = mock_orchestrator.return_value
        mock_orch_inst.evaluate_trade.return_value = {
            "filters": {"governance_approved": True}
        }
        mock_orch_inst.session_id = "session1"
        mock_exec_gate_inst = mock_exec_gate.return_value
        mock_exec_gate_inst.evaluate_trade.return_value = {
            "decision": {"final": "ALLOW"}
        }

        result = execute_mobile_trade_ticket(user_ctx, form)

        assert result["ok"] is True
        call_kwargs = mock_exec_gate_inst.evaluate_trade.call_args[1]
        assert call_kwargs["equity"] == 10000.0
        assert call_kwargs["equity_peak"] == 10000.0
