from __future__ import annotations

import pytest
from typing import Any

from backend.trading.trade_quality_scoring_engine import (
    TradeQualityScoringEngine,
    TradeQualityScoringEngineError,
)


def test_excellent_trade() -> None:
    engine = TradeQualityScoringEngine()
    candidate = {
        "trade_id": "t-excellent",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "expected_edge": 0.08,
        "risk_reward": 3.5,
        "signal_agreement": 0.95,
        "historical_reliability": 0.90,
        "market_regime": "TRENDING",
    }
    market_metrics = {
        "current_regime": "TRENDING",
        "liquidity_rating": "HIGH",
        "spread": 0.0001,
        "volatility_suitability": True,
    }

    result = engine.score_trade(candidate, market_metrics)

    assert result["trade_quality_score"] >= 90.0
    assert result["quality_grade"] == "A"
    assert "expected_edge" in result["dimension_scores"]
    assert result["dimension_scores"]["expected_edge"] == 100.0
    assert result["dimension_scores"]["risk_reward_ratio"] == 100.0
    
    # Strengths should be populated
    assert "Strong Expected Edge" in result["strengths"]
    assert "Excellent Risk/Reward Profile" in result["strengths"]
    assert "High Signal Agreement" in result["strengths"]
    assert "Strong Historical Strategy Reliability" in result["strengths"]
    assert "Excellent Market Regime Alignment" in result["strengths"]
    assert "High Liquidity Quality" in result["strengths"]
    assert "Tight Bid-Ask Spread" in result["strengths"]
    assert "Suitable Volatility Environment" in result["strengths"]
    assert len(result["weaknesses"]) == 0


def test_average_trade() -> None:
    engine = TradeQualityScoringEngine()
    candidate = {
        "trade_id": "t-average",
        "symbol": "EURUSD",
        "asset_class": "fx",
        "expected_edge": 0.035,
        "risk_reward": 1.8,
        "signal_agreement": 0.70,
        "historical_reliability": 0.75,
        "market_regime": "RANGING",
    }
    market_metrics = {
        "current_regime": "RANGING",
        "liquidity_rating": "MEDIUM",
        "spread": 0.0015,
        "volatility_suitability": 0.75,
    }

    result = engine.score_trade(candidate, market_metrics)

    assert 70.0 <= result["trade_quality_score"] < 80.0
    assert result["quality_grade"] == "C"
    assert len(result["weaknesses"]) == 0


def test_poor_quality_trade() -> None:
    engine = TradeQualityScoringEngine()
    candidate = {
        "trade_id": "t-poor",
        "symbol": "AAPL",
        "asset_class": "equities",
        "expected_value": 10.0,
        "cost": 12.0,  # Negative edge
        "risk_reward": 0.3,
        "signal_agreement": 0.20,
        "historical_reliability": 0.40,
        "market_regime": "TRENDING",
    }
    market_metrics = {
        "current_regime": "RANGING",  # regime mismatch
        "liquidity_rating": "LOW",
        "spread": 0.0045,  # large spread close to 0.005 limit
        "volatility_suitability": False,
    }

    result = engine.score_trade(candidate, market_metrics)

    assert result["trade_quality_score"] < 40.0
    assert result["quality_grade"] == "F"
    
    # Weaknesses should be populated
    assert "Weak Expected Edge" in result["weaknesses"]
    assert "Poor Risk/Reward Profile" in result["weaknesses"]
    assert "Weak Signal Agreement" in result["weaknesses"]
    assert "Low Historical Strategy Reliability" in result["weaknesses"]
    assert "Poor Market Regime Alignment" in result["weaknesses"]
    assert "Low Liquidity Quality" in result["weaknesses"]
    assert "Wide Bid-Ask Spread" in result["weaknesses"]
    assert "Unsuitable Volatility Environment" in result["weaknesses"]
    assert len(result["strengths"]) == 0


def test_low_liquidity_trade() -> None:
    engine = TradeQualityScoringEngine()
    candidate = {
        "trade_id": "t-low-liq",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "expected_edge": 0.08,
        "risk_reward": 3.5,
        "signal_agreement": 0.95,
        "historical_reliability": 0.90,
        "market_regime": "TRENDING",
    }
    market_metrics = {
        "current_regime": "TRENDING",
        "liquidity_rating": "LOW",  # Low liquidity
        "spread": 0.0001,
        "volatility_suitability": True,
    }

    result = engine.score_trade(candidate, market_metrics)
    assert result["dimension_scores"]["liquidity_quality"] == 30.0
    assert "Low Liquidity Quality" in result["weaknesses"]


def test_high_spread_trade() -> None:
    engine = TradeQualityScoringEngine()
    candidate = {
        "trade_id": "t-high-spread",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "expected_edge": 0.08,
        "risk_reward": 3.5,
        "signal_agreement": 0.95,
        "historical_reliability": 0.90,
        "market_regime": "TRENDING",
    }
    market_metrics = {
        "current_regime": "TRENDING",
        "liquidity_rating": "HIGH",
        "spread": 0.0048,  # very large spread (max is 0.005)
        "volatility_suitability": True,
    }

    result = engine.score_trade(candidate, market_metrics)
    # Score should be low for spread
    assert result["dimension_scores"]["spread_quality"] == 4.0
    assert "Wide Bid-Ask Spread" in result["weaknesses"]


def test_regime_mismatch() -> None:
    engine = TradeQualityScoringEngine()
    candidate = {
        "trade_id": "t-mismatch",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "expected_edge": 0.08,
        "risk_reward": 3.5,
        "signal_agreement": 0.95,
        "historical_reliability": 0.90,
        "market_regime": "TRENDING",
    }
    market_metrics = {
        "current_regime": "RANGING",  # mismatch
        "liquidity_rating": "HIGH",
        "spread": 0.0001,
        "volatility_suitability": True,
    }

    result = engine.score_trade(candidate, market_metrics)
    assert result["dimension_scores"]["market_regime_alignment"] == 20.0
    assert "Poor Market Regime Alignment" in result["weaknesses"]


def test_invalid_input_fail_closed() -> None:
    engine = TradeQualityScoringEngine()

    # Input not a mapping
    with pytest.raises(TradeQualityScoringEngineError, match="candidate must be a Mapping"):
        engine.score_trade("not-a-dict", {})  # type: ignore

    with pytest.raises(TradeQualityScoringEngineError, match="market_metrics must be a Mapping"):
        engine.score_trade({}, "not-a-dict")  # type: ignore

    # Missing required trade identifier fields
    with pytest.raises(TradeQualityScoringEngineError, match="Missing or empty required field: trade_id"):
        engine.score_trade({"symbol": "BTCUSD", "asset_class": "crypto"}, {})

    with pytest.raises(TradeQualityScoringEngineError, match="Missing or empty required field: symbol"):
        engine.score_trade({"trade_id": "t1", "asset_class": "crypto"}, {})

    with pytest.raises(TradeQualityScoringEngineError, match="Missing or empty required field: asset_class"):
        engine.score_trade({"trade_id": "t1", "symbol": "BTCUSD"}, {})

    # Malformed numeric values
    candidate = {
        "trade_id": "t-malformed",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "expected_edge": "extremely-high",  # invalid float
        "risk_reward": 3.5,
        "signal_agreement": 0.95,
        "historical_reliability": 0.90,
        "market_regime": "TRENDING",
    }
    market_metrics = {
        "current_regime": "TRENDING",
        "liquidity_rating": "HIGH",
        "spread": 0.0001,
        "volatility_suitability": True,
    }
    with pytest.raises(TradeQualityScoringEngineError, match="Field expected_edge must be numeric"):
        engine.score_trade(candidate, market_metrics)


def test_deterministic_scoring() -> None:
    engine = TradeQualityScoringEngine()
    candidate = {
        "trade_id": "t-det",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "expected_edge": 0.04,
        "risk_reward": 2.5,
        "signal_agreement": 0.85,
        "historical_reliability": 0.80,
        "market_regime": "TRENDING",
    }
    market_metrics = {
        "current_regime": "TRENDING",
        "liquidity_rating": "HIGH",
        "spread": 0.0005,
        "volatility_suitability": True,
    }

    result1 = engine.score_trade(candidate, market_metrics)
    result2 = engine.score_trade(candidate, market_metrics)

    assert result1["trade_quality_score"] == result2["trade_quality_score"]
    assert result1["dimension_scores"] == result2["dimension_scores"]
    assert result1["strengths"] == result2["strengths"]
    assert result1["weaknesses"] == result2["weaknesses"]
    assert result1["quality_grade"] == result2["quality_grade"]


def test_advisory_only_output() -> None:
    engine = TradeQualityScoringEngine()
    candidate = {
        "trade_id": "t-adv",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "expected_edge": 0.04,
        "risk_reward": 2.5,
        "signal_agreement": 0.85,
        "historical_reliability": 0.80,
        "market_regime": "TRENDING",
    }
    market_metrics = {
        "current_regime": "TRENDING",
        "liquidity_rating": "HIGH",
        "spread": 0.0005,
        "volatility_suitability": True,
    }

    result = engine.score_trade(candidate, market_metrics)

    assert result["advisory_only"] is True
    assert result["shadow_mode"] is True
    assert result["execution_action"] == "NO_EXECUTION"
