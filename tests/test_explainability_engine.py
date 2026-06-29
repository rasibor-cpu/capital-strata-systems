from __future__ import annotations

from backend.portfolio.explainability_engine import ExplainabilityEngine


def test_explainability_engine_generates_traceable_reasons() -> None:
    result = ExplainabilityEngine().explain(
        portfolio_intelligence={
            "portfolio_status": "WATCH",
            "intelligence_score": 68,
            "explainability": ["High drawdown is reducing portfolio readiness."],
        },
        adaptive_portfolio={
            "adaptive_recommendation": "REDUCE_RISK",
            "primary_drivers": ["Portfolio intelligence is mixed."],
        },
        risk_committee={"committee_decision": "APPROVE_WITH_CAUTION", "committee_status": "AMBER", "concerns": ["weak_attribution"]},
        quantitative_metrics={"status": "OK", "metrics": {"rolling_sharpe": 0.5, "rolling_sortino": 0.7, "max_drawdown": 0.12}},
        market_regime={"detected_regime": "HIGH_VOLATILITY", "risk_bias": "DEFENSIVE"},
        policy_profile={"active_profile": "CONSERVATIVE"},
        validation={"validation_status": "WARN", "warnings": ["cash_reserve_below_policy"], "violations": []},
        consistency={"consistent": False, "conflicts": ["adaptive_increase_conflicts_with_red_committee"]},
    )

    assert result["status"] == "OK"
    assert result["primary_explanation"] == "Adaptive portfolio recommendation is REDUCE_RISK."
    assert any("High drawdown" in item for item in result["explanation"])
    assert any("Conflicting signal" in item for item in result["explanation"])
    assert result["advisory_only"] is True


def test_explainability_engine_fails_closed_when_inputs_missing() -> None:
    result = ExplainabilityEngine().explain()

    assert result["explanation"] == ["Advisory evidence is unavailable; fail closed."]
    assert result["advisory_only"] is True
