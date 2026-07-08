from __future__ import annotations

import pytest
from backend.analytics.trade_outcome_attribution import (
    TradeOutcomeAttributionEngine,
    TradeOutcomeAttributionError,
)


def test_excellent_winning_trade() -> None:
    engine = TradeOutcomeAttributionEngine()
    completed_trade = {
        "trade_id": "t1",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "realized_pnl": 500.0,
        "market_regime": "TRENDING",
    }
    quality_output = {
        "trade_quality_score": 90.0,
        "strengths": ["Strong Expected Edge"],
        "weaknesses": [],
    }
    execution_output = {
        "execution_quality_score": 92.0,
        "slippage_bps": 0.0,
        "latency_ms": 30.0,
        "spread_bps": 1.0,
    }
    market_regime = "TRENDING"

    result = engine.attribute_outcome(
        completed_trade=completed_trade,
        quality_output=quality_output,
        execution_output=execution_output,
        market_regime=market_regime,
    )

    assert result["overall_attribution_score"] == 90.0
    assert result["execution_contribution"] > 0.0
    assert result["trade_quality_contribution"] > 0.0
    assert result["regime_contribution"] == 50.0
    assert result["timing_contribution"] > 0.0
    assert "Optimal Trade Quality" in result["primary_success_factors"]
    assert "Excellent Execution Quality" in result["primary_success_factors"]
    assert "Favorable Market Regime Alignment" in result["primary_success_factors"]
    assert "Efficient Execution Timing" in result["primary_success_factors"]
    assert len(result["primary_failure_factors"]) == 0
    assert "WINNING" in result["attribution_summary"]


def test_poor_losing_trade() -> None:
    engine = TradeOutcomeAttributionEngine()
    completed_trade = {
        "trade_id": "t2",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "realized_pnl": -300.0,
        "market_regime": "TRENDING",
    }
    quality_output = {
        "trade_quality_score": 40.0,
        "strengths": [],
        "weaknesses": ["Weak Expected Edge"],
    }
    explanation_output = {
        "opposing_factors": ["Regime Mismatch Detected", "High Portfolio Risk Level"],
    }
    execution_output = {
        "execution_quality_score": 40.0,
        "slippage_bps": 30.0,
        "latency_ms": 600.0,
    }

    result = engine.attribute_outcome(
        completed_trade=completed_trade,
        quality_output=quality_output,
        explanation_output=explanation_output,
        execution_output=execution_output,
    )

    # 100 - 40 = 60.0 (correctly predicted failure)
    assert result["overall_attribution_score"] == 60.0
    assert result["trade_quality_contribution"] < 0.0
    assert result["execution_contribution"] < 0.0
    assert result["regime_contribution"] == -50.0
    assert result["risk_contribution"] == -40.0
    assert result["timing_contribution"] < 0.0
    assert "Poor Trade Quality" in result["primary_failure_factors"]
    assert "Poor Execution Quality" in result["primary_failure_factors"]
    assert "Market Regime Mismatch" in result["primary_failure_factors"]
    assert "Elevated Risk Parameters" in result["primary_failure_factors"]
    assert "Inefficient Execution Timing / Latency" in result["primary_failure_factors"]
    assert len(result["primary_success_factors"]) == 0
    assert "LOSING" in result["attribution_summary"]


def test_excellent_execution_poor_outcome() -> None:
    engine = TradeOutcomeAttributionEngine()
    completed_trade = {
        "trade_id": "t3",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "realized_pnl": -150.0,
    }
    quality_output = {
        "trade_quality_score": 75.0,
    }
    execution_output = {
        "execution_quality_score": 95.0,
        "slippage_bps": 0.0,
        "latency_ms": 20.0,
    }

    result = engine.attribute_outcome(
        completed_trade=completed_trade,
        quality_output=quality_output,
        execution_output=execution_output,
    )

    assert result["execution_contribution"] > 0.0
    assert "Poor Execution Quality" not in result["primary_failure_factors"]


def test_poor_execution_good_outcome() -> None:
    engine = TradeOutcomeAttributionEngine()
    completed_trade = {
        "trade_id": "t4",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "realized_pnl": 200.0,
    }
    quality_output = {
        "trade_quality_score": 85.0,
    }
    execution_output = {
        "execution_quality_score": 35.0,
        "slippage_bps": 40.0,
        "latency_ms": 800.0,
    }

    result = engine.attribute_outcome(
        completed_trade=completed_trade,
        quality_output=quality_output,
        execution_output=execution_output,
    )

    # Even though it's a win, execution contribution is negative
    assert result["execution_contribution"] < 0.0
    assert "Excellent Execution Quality" not in result["primary_success_factors"]


def test_regime_mismatch() -> None:
    engine = TradeOutcomeAttributionEngine()
    completed_trade = {
        "trade_id": "t5",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "realized_pnl": -50.0,
        "market_regime": "TRENDING",
    }
    market_regime = "RANGING"

    result = engine.attribute_outcome(
        completed_trade=completed_trade,
        market_regime=market_regime,
    )

    assert result["regime_contribution"] == -50.0
    assert "Market Regime Mismatch" in result["primary_failure_factors"]


def test_missing_optional_contexts() -> None:
    engine = TradeOutcomeAttributionEngine()
    completed_trade = {
        "trade_id": "t6",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "realized_pnl": 100.0,
    }

    result = engine.attribute_outcome(
        completed_trade=completed_trade,
        quality_output=None,
        explanation_output=None,
        execution_output=None,
        market_regime=None,
        execution_metrics=None,
        risk_metrics=None,
    )

    assert result["trade_quality_contribution"] == 0.0
    assert result["execution_contribution"] == 0.0
    assert result["regime_contribution"] == 0.0
    assert result["timing_contribution"] == 0.0
    assert result["overall_attribution_score"] == 70.0  # base neutral prediction
    assert len(result["lessons_learned"]) > 0


def test_invalid_inputs_fail_closed() -> None:
    engine = TradeOutcomeAttributionEngine()

    # Invalid Mapping
    with pytest.raises(TradeOutcomeAttributionError, match="completed_trade must be a Mapping"):
        engine.attribute_outcome("not-a-dict")  # type: ignore

    # Missing fields
    with pytest.raises(TradeOutcomeAttributionError, match="Missing or empty required field in completed_trade: trade_id"):
        engine.attribute_outcome({"symbol": "BTCUSD", "asset_class": "crypto", "realized_pnl": 100.0})

    with pytest.raises(TradeOutcomeAttributionError, match="Missing or empty required field in completed_trade: symbol"):
        engine.attribute_outcome({"trade_id": "tx", "asset_class": "crypto", "realized_pnl": 100.0})

    with pytest.raises(TradeOutcomeAttributionError, match="Missing or empty required field in completed_trade: asset_class"):
        engine.attribute_outcome({"trade_id": "tx", "symbol": "BTCUSD", "realized_pnl": 100.0})

    # Missing PnL
    with pytest.raises(TradeOutcomeAttributionError, match="Realized PnL is required for outcome attribution"):
        engine.attribute_outcome({"trade_id": "tx", "symbol": "BTCUSD", "asset_class": "crypto"})


def test_deterministic_output() -> None:
    engine = TradeOutcomeAttributionEngine()
    completed_trade = {
        "trade_id": "t_det",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "realized_pnl": 150.0,
    }

    result1 = engine.attribute_outcome(completed_trade=completed_trade)
    result2 = engine.attribute_outcome(completed_trade=completed_trade)

    assert result1 == result2


def test_advisory_only_contract() -> None:
    engine = TradeOutcomeAttributionEngine()
    completed_trade = {
        "trade_id": "t_adv",
        "symbol": "BTCUSD",
        "asset_class": "crypto",
        "realized_pnl": 150.0,
    }

    result = engine.attribute_outcome(completed_trade=completed_trade)

    assert result["advisory_only"] is True
    assert result["shadow_mode"] is True
    assert result["execution_action"] == "NO_EXECUTION"
