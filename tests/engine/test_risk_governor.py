from __future__ import annotations

import logging

from engine.execution.execution_gate import ExecutionGate
from backend.app.risk.anti_bleed_guard import AntiBleedGuard
from engine.risk.risk_governor import RiskGovernor
from engine.risk.margin_snapshot import MarginSnapshot, MarginState


class StaticEquityAuthority:
    def __init__(self, equity: float, peak: float) -> None:
        self._equity = equity
        self._peak = peak

    def current_equity(self) -> float:
        return self._equity

    def peak_equity(self) -> float:
        return self._peak


def test_allow_trade_approves_normal_path_with_shape() -> None:
    decision = RiskGovernor().allow_trade(
        instrument="EUR_USD",
        side="BUY",
        notional=100.0,
        stop_distance_pct=0.02,
        equity=10000.0,
    )

    assert decision.ok is True
    assert decision.status in {"APPROVED", "APPROVED_WITH_ADJUSTMENT"}
    assert decision.requested_notional == 100.0
    assert decision.recommended_notional > 0.0
    assert decision.equity_risk > 0.0
    assert set(decision.as_dict()) == {
        "ok",
        "status",
        "reason",
        "requested_notional",
        "recommended_notional",
        "equity_risk",
        "risk_pct",
        "adjusted",
    }


def test_allow_trade_rejects_hard_drawdown() -> None:
    decision = RiskGovernor(
        equity_authority=StaticEquityAuthority(equity=79.0, peak=100.0)
    ).allow_trade(
        instrument="EUR_USD",
        side="BUY",
        notional=100.0,
        stop_distance_pct=0.02,
    )

    assert decision.ok is False
    assert decision.status == "REJECTED"
    assert decision.reason == "hard_drawdown_limit_reached"
    assert decision.recommended_notional == 0.0


def test_allow_trade_fails_safe_when_equity_missing() -> None:
    decision = RiskGovernor().allow_trade(
        instrument="EUR_USD",
        side="BUY",
        notional=100.0,
        stop_distance_pct=0.02,
    )

    assert decision.ok is False
    assert decision.status == "REJECTED"
    assert decision.reason == "equity_missing"


def test_validate_trade_adapter_contract_and_risk_cap() -> None:
    result = RiskGovernor().validate_trade(
        instrument="EUR_USD",
        side="BUY",
        requested_notional=5000.0,
        stop_distance_pct=0.05,
        equity=10000.0,
        risk_pct=0.50,
    )

    assert result["ok"] is True
    assert result["status"] == "APPROVED_WITH_ADJUSTMENT"
    assert result["risk_pct"] == RiskGovernor.MAX_RISK_PCT
    assert result["recommended_notional"] == 4000.0
    assert set(result) == {
        "ok",
        "status",
        "reason",
        "requested_notional",
        "recommended_notional",
        "equity_risk",
        "risk_pct",
        "adjusted",
    }


def test_validate_trade_fails_safe_for_invalid_inputs() -> None:
    result = RiskGovernor().validate_trade(
        instrument="EUR_USD",
        side="BUY",
        requested_notional=100.0,
        stop_distance_pct=0.0,
        equity=10000.0,
        risk_pct=0.01,
    )

    assert result["ok"] is False
    assert result["status"] == "REJECTED"
    assert result["reason"] == "invalid_stop_distance"


def test_validate_trade_exposes_lower_information_adapter_path(caplog) -> None:
    RiskGovernor._LOW_INFO_VALIDATION_WARNED = False
    caplog.set_level(logging.WARNING, logger="engine.risk.risk_governor")

    result = RiskGovernor().validate_trade(
        instrument="EUR_USD",
        side="BUY",
        requested_notional=10000.0,
        stop_distance_pct=0.01,
        equity=10000.0,
        risk_pct=RiskGovernor.BASE_RISK_PCT,
        regime_persistence=0.2,
        vol_ratio=2.0,
        spread_bps=10.0,
        high_risk_news=True,
    )

    assert result["ok"] is True
    assert result["recommended_notional"] == 5000.0
    assert "lower-information adapter path" in caplog.text
    assert "ignored_context" in caplog.text


def test_allow_trade_applies_context_that_validate_trade_expects_upstream() -> None:
    governor = RiskGovernor()

    allow_decision = governor.allow_trade(
        instrument="EUR_USD",
        side="BUY",
        notional=10000.0,
        stop_distance_pct=0.01,
        equity=10000.0,
        regime_persistence=0.2,
        vol_ratio=2.0,
        spread_bps=10.0,
        high_risk_news=True,
    )
    validate_result = governor.validate_trade(
        instrument="EUR_USD",
        side="BUY",
        requested_notional=10000.0,
        stop_distance_pct=0.01,
        equity=10000.0,
        risk_pct=RiskGovernor.BASE_RISK_PCT,
        regime_persistence=0.2,
        vol_ratio=2.0,
        spread_bps=10.0,
        high_risk_news=True,
    )

    assert allow_decision.ok is True
    assert allow_decision.recommended_notional == 187.5
    assert validate_result["recommended_notional"] == 5000.0


def test_execution_gate_marks_precomputed_risk_governor_path(tmp_path) -> None:
    guard = AntiBleedGuard(
        cooldown_minutes=0,
        state_file=str(tmp_path / "anti_bleed_state.json"),
    )

    result = ExecutionGate(anti_bleed_guard=guard).evaluate_trade(
        instrument="EUR_USD",
        side="BUY",
        notional=100.0,
        stop_distance_pct=0.02,
        equity=10000.0,
        equity_peak=10000.0,
        regime_persistence=1.0,
        expected_move_bps=80.0,
        fee_bps=1.0,
        spread_bps=1.0,
        slippage_bps=1.0,
        price=1.10,
        price_instrument="EUR_USD",
        margin_snapshot=MarginSnapshot(
            broker="TEST",
            account_id="123",
            timestamp="2026-06-17T00:00:00Z",
            equity=10000.0,
            cash=10000.0,
            buying_power=5000.0,
            maintenance_margin=2500.0,
            initial_margin=5000.0,
            margin_used=0.0,
            margin_available=10000.0,
            margin_ratio=0.0,
            margin_state=MarginState.NORMAL
        ),
        broker_mode="PAPER",
    )

    assert result["debug"]["anti_bleed_guard"]["approved"] is True
    assert result["debug"]["margin_trade_gate"]["allowed"] is True
    assert result["debug"]["riskgov_path"] == "validate_trade_precomputed_risk_pct"
    assert "governor_response" in result["debug"]
