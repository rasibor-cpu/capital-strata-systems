from __future__ import annotations

from backend.execution.canonical_execution_integration import CanonicalExecutionIntegration


class _GateApproved:
    def approve_trade(self, candidate, session, portfolio_state, engine_mode):
        from backend.governance.css_unified_trade_gate import GateDecision

        return GateDecision(
            approved=True,
            reason="approved",
            engine_mode=engine_mode,
            timestamp=1.0,
            details={},
        )


class _GateBlocked:
    def approve_trade(self, candidate, session, portfolio_state, engine_mode):
        from backend.governance.css_unified_trade_gate import GateDecision

        return GateDecision(
            approved=False,
            reason="blocked",
            engine_mode=engine_mode,
            timestamp=1.0,
            details={},
        )


class _ExecutionGateAllow:
    def evaluate_trade(self, **kwargs):
        return {"decision": {"final": "ALLOW"}, "reason": "approved"}


class _ExecutionGateBlock:
    def evaluate_trade(self, **kwargs):
        return {"decision": {"final": "BLOCK"}, "reason": "risk_reject"}


def _request() -> dict[str, object]:
    return {
        "asset_class": "FX",
        "symbol": "EUR/USD",
        "side": "BUY",
        "quantity": 1,
        "mode": "paper",
    }


def _context() -> dict[str, object]:
    return {
        "instrument": "EUR_USD",
        "side": "BUY",
        "notional": 1000.0,
        "stop_distance_pct": 0.01,
        "equity": 100000.0,
        "equity_peak": 100000.0,
        "regime_persistence": 0.5,
        "policy": "core",
        "volatility_state": "MEDIUM",
        "expected_move_bps": 12.0,
        "fee_bps": 0.5,
        "spread_bps": 1.0,
        "slippage_bps": 0.5,
        "margin_snapshot": {"available_margin": 100000.0},
        "broker_mode": "PAPER",
    }


def test_canonical_execution_approved_route() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateApproved(),
        execution_gate=_ExecutionGateAllow(),
    )

    result = integration.execute(
        engine_run_id="run-1",
        canonical_decision={"decision": "ALLOW"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request(),
        execution_context=_context(),
    )

    assert result.execution_decision["can_execute"] is True
    assert result.execution_decision["final_decision"] == "ALLOW"
    assert result.execution_result["status"] == "accepted"


def test_canonical_execution_blocked_by_governance() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateBlocked(),
        execution_gate=_ExecutionGateAllow(),
    )

    result = integration.execute(
        engine_run_id="run-2",
        canonical_decision={"decision": "BLOCK"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request(),
        execution_context=_context(),
    )

    assert result.execution_decision["can_execute"] is False
    assert result.execution_decision["final_decision"] == "BLOCK"
    assert result.execution_result["status"] == "blocked"


def test_canonical_execution_blocked_by_execution_gate() -> None:
    integration = CanonicalExecutionIntegration(
        trade_gate=_GateApproved(),
        execution_gate=_ExecutionGateBlock(),
    )

    result = integration.execute(
        engine_run_id="run-3",
        canonical_decision={"decision": "BLOCK"},
        candidate={"asset_class": "fx", "expected_value": 2.0, "cost": 1.0, "probability": 0.8},
        session={"created": 0.0, "role": "ADMIN"},
        portfolio_state={"fx": 0},
        engine_mode="BALANCED",
        execution_request=_request(),
        execution_context=_context(),
    )

    assert result.execution_decision["can_execute"] is False
    assert result.execution_decision["blocked_by"] == ["execution_gate"]
