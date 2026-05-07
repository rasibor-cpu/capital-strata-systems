from __future__ import annotations

from engine.risk.risk_governor import RiskGovernor


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

