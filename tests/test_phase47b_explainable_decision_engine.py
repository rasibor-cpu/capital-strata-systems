from __future__ import annotations

import pytest
from backend.analytics.explainable_decision_engine import (
    ExplainableDecisionEngine,
    ExplainableDecisionEngineError,
)


def test_excellent_explained_decision() -> None:
    engine = ExplainableDecisionEngine()
    candidate = {
        "trade_id": "t1",
        "symbol": "AAPL",
        "asset_class": "EQUITIES",
        "market_regime": "TRENDING",
    }
    quality_output = {
        "trade_quality_score": 95.0,
        "quality_grade": "A",
        "dimension_scores": {},
        "strengths": ["Strong Expected Edge", "Excellent Risk/Reward Profile"],
        "weaknesses": [],
    }
    signal_context = {"signal_strength": 0.90}
    risk_context = {"risk_level": "LOW", "concentration_risk": 0.1}
    regime_context = {"current_regime": "TRENDING"}
    market_metrics = {
        "liquidity_rating": "HIGH",
        "spread": 0.0001,
        "volatility_suitability": True,
    }

    result = engine.explain_decision(
        candidate=candidate,
        quality_output=quality_output,
        signal_context=signal_context,
        risk_context=risk_context,
        regime_context=regime_context,
        market_metrics=market_metrics,
    )

    assert result["explanation_score"] == 95.0
    assert result["quality_grade"] == "A"
    assert "Strong Expected Edge" in result["supporting_factors"]
    assert "Excellent Risk/Reward Profile" in result["supporting_factors"]
    assert "High Trade Quality Assessment" in result["supporting_factors"]
    assert "Strong Signal Strength Confirmation" in result["supporting_factors"]
    assert "Aligned Market Regime" in result["supporting_factors"]
    assert "Acceptable Risk Levels" in result["supporting_factors"]
    assert "Optimal Market Conditions" in result["supporting_factors"]
    assert len(result["opposing_factors"]) == 0
    assert "fully supported by the available metrics" in result["decision_summary"]


def test_poor_explained_decision() -> None:
    engine = ExplainableDecisionEngine()
    candidate = {
        "trade_id": "t2",
        "symbol": "AAPL",
        "asset_class": "EQUITIES",
        "market_regime": "TRENDING",
    }
    quality_output = {
        "trade_quality_score": 45.0,
        "quality_grade": "F",
        "dimension_scores": {},
        "strengths": [],
        "weaknesses": ["Weak Expected Edge"],
    }
    signal_context = {"signal_strength": 0.20}
    risk_context = {"risk_level": "HIGH", "concentration_risk": 0.7}
    regime_context = {"current_regime": "RANGING"}
    market_metrics = {
        "liquidity_rating": "LOW",
        "spread": 0.006,
        "volatility_suitability": False,
    }

    result = engine.explain_decision(
        candidate=candidate,
        quality_output=quality_output,
        signal_context=signal_context,
        risk_context=risk_context,
        regime_context=regime_context,
        market_metrics=market_metrics,
    )

    assert result["explanation_score"] == 45.0
    assert result["quality_grade"] == "F"
    assert "Weak Expected Edge" in result["opposing_factors"]
    assert "Low Trade Quality Assessment" in result["opposing_factors"]
    assert "Weak Signal Strength" in result["opposing_factors"]
    assert "High Portfolio Risk Level" in result["opposing_factors"]
    assert "High Concentration Risk" in result["opposing_factors"]
    assert "Regime Mismatch Detected" in result["opposing_factors"]
    assert "Low Liquidity Quality" in result["opposing_factors"]
    assert "Wide Bid-Ask Spread" in result["opposing_factors"]
    assert "Unsuitable Volatility Environment" in result["opposing_factors"]
    assert len(result["supporting_factors"]) == 0
    assert "Warnings or detractors were identified" in result["decision_summary"]


def test_regime_mismatch() -> None:
    engine = ExplainableDecisionEngine()
    candidate = {
        "trade_id": "t3",
        "symbol": "AAPL",
        "asset_class": "EQUITIES",
        "market_regime": "TRENDING",
    }
    regime_context = {"current_regime": "RANGING"}

    result = engine.explain_decision(candidate=candidate, regime_context=regime_context)

    # Base 70 - 30 (mismatch) = 40.0
    assert result["explanation_score"] == 40.0
    assert result["quality_grade"] == "F"
    assert "Regime Mismatch Detected" in result["opposing_factors"]
    assert "Regime Mismatch Detected" in result["confidence_detractors"]
    assert "Regime mismatch: candidate expects TRENDING but current regime is RANGING" in result["regime_notes"]


def test_risk_concerns() -> None:
    engine = ExplainableDecisionEngine()
    candidate = {
        "trade_id": "t4",
        "symbol": "AAPL",
        "asset_class": "EQUITIES",
    }
    risk_context = {
        "risk_level": "HIGH",
        "concentration_risk": 0.8,
    }

    result = engine.explain_decision(candidate=candidate, risk_context=risk_context)

    assert "High Portfolio Risk Level" in result["opposing_factors"]
    assert "High Concentration Risk" in result["opposing_factors"]
    assert "Risk level is marked as HIGH" in result["risk_notes"]
    assert "Concentration risk is elevated: 0.8" in result["risk_notes"]


def test_poor_liquidity_spread_conditions() -> None:
    engine = ExplainableDecisionEngine()
    candidate = {
        "trade_id": "t5",
        "symbol": "AAPL",
        "asset_class": "EQUITIES",
    }
    market_metrics = {
        "liquidity_rating": "LOW",
        "spread": 0.008,
        "volatility_suitability": False,
    }

    result = engine.explain_decision(candidate=candidate, market_metrics=market_metrics)

    assert "Low Liquidity Quality" in result["opposing_factors"]
    assert "Wide Bid-Ask Spread" in result["opposing_factors"]
    assert "Unsuitable Volatility Environment" in result["opposing_factors"]
    assert "Market liquidity rating is LOW" in result["market_notes"]
    assert "exceeds or matches maximum threshold" in result["market_notes"]


def test_missing_optional_context() -> None:
    engine = ExplainableDecisionEngine()
    candidate = {
        "trade_id": "t6",
        "symbol": "AAPL",
        "asset_class": "EQUITIES",
    }

    result = engine.explain_decision(
        candidate=candidate,
        quality_output=None,
        signal_context=None,
        risk_context=None,
        regime_context=None,
        market_metrics=None,
    )

    # Ensure no crashes and returns deterministic values
    assert result["explanation_score"] == 70.0
    assert result["quality_grade"] == "C"
    assert "Risk context unavailable: no risk evaluation performed" in result["risk_notes"]
    assert "Regime context unavailable: no regime alignment verification performed" in result["regime_notes"]
    assert "Market metrics unavailable: no market condition checks performed" in result["market_notes"]


def test_invalid_candidate_fail_closed() -> None:
    engine = ExplainableDecisionEngine()

    with pytest.raises(ExplainableDecisionEngineError, match="candidate must be a Mapping"):
        engine.explain_decision("not-a-dict")  # type: ignore

    with pytest.raises(ExplainableDecisionEngineError, match="Missing or empty required field in candidate: trade_id"):
        engine.explain_decision({"symbol": "AAPL", "asset_class": "EQUITIES"})

    with pytest.raises(ExplainableDecisionEngineError, match="Missing or empty required field in candidate: symbol"):
        engine.explain_decision({"trade_id": "t1", "asset_class": "EQUITIES"})

    with pytest.raises(ExplainableDecisionEngineError, match="Missing or empty required field in candidate: asset_class"):
        engine.explain_decision({"trade_id": "t1", "symbol": "AAPL"})


def test_deterministic_output() -> None:
    engine = ExplainableDecisionEngine()
    candidate = {
        "trade_id": "td",
        "symbol": "AAPL",
        "asset_class": "EQUITIES",
    }
    risk_context = {"risk_level": "LOW"}
    market_metrics = {"liquidity_rating": "HIGH"}

    result1 = engine.explain_decision(candidate=candidate, risk_context=risk_context, market_metrics=market_metrics)
    result2 = engine.explain_decision(candidate=candidate, risk_context=risk_context, market_metrics=market_metrics)

    assert result1 == result2


def test_advisory_only_output() -> None:
    engine = ExplainableDecisionEngine()
    candidate = {
        "trade_id": "t_adv",
        "symbol": "AAPL",
        "asset_class": "EQUITIES",
    }

    result = engine.explain_decision(candidate=candidate)

    assert result["advisory_only"] is True
    assert result["shadow_mode"] is True
    assert result["execution_action"] == "NO_EXECUTION"
