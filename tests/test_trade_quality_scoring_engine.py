from __future__ import annotations

import pytest

from backend.analytics.trade_quality_scoring_engine import (
    TradeQualityScoringEngine,
    TradeQualityScoringEngineError,
)


def _candidate(**overrides):
    base = {
        "trade_id": "t-1",
        "symbol": "AAPL",
        "asset_class": "EQUITY",
        "market_regime": "TRENDING",
        "strategy_score": 0.9,
        "replay_confidence": 0.92,
        "concentration_risk": 0.15,
        "allocation_weight": 0.25,
        "allocation_amount": 2500.0,
        "available_capital": 10000.0,
        "recommended_position_size": 2000.0,
        "exit_action": "TRAIL",
        "exit_confidence": 0.85,
        "risk_reward": 2.3,
    }
    base.update(overrides)
    return base


def test_high_quality_scores_execute_or_preferred() -> None:
    engine = TradeQualityScoringEngine()
    assessment = engine.score_candidate(_candidate())

    assert assessment.quality_score >= 65.0
    assert assessment.recommendation in {"EXECUTE", "PREFERRED"}


def test_weak_trade_scores_reject() -> None:
    engine = TradeQualityScoringEngine()
    assessment = engine.score_candidate(
        _candidate(
            market_regime="UNKNOWN",
            strategy_score=0.05,
            replay_confidence=0.05,
            concentration_risk=0.95,
            allocation_weight=0.0,
            recommended_position_size=0.0,
            exit_action="STOP_LOSS",
            risk_reward=0.2,
        )
    )

    assert assessment.quality_score < 45.0
    assert assessment.recommendation == "REJECT"


def test_marginal_trade_scores_watch() -> None:
    engine = TradeQualityScoringEngine()
    assessment = engine.score_candidate(
        _candidate(
            market_regime="RANGING",
            strategy_score=0.5,
            replay_confidence=0.5,
            concentration_risk=0.5,
            allocation_weight=0.15,
            recommended_position_size=900.0,
            exit_action="REDUCE",
            risk_reward=1.0,
        )
    )

    assert 45.0 <= assessment.quality_score < 65.0
    assert assessment.recommendation == "WATCH"


def test_invalid_input_fail_closed() -> None:
    engine = TradeQualityScoringEngine()

    with pytest.raises(TradeQualityScoringEngineError):
        engine.score_candidate({"trade_id": "x"})

    with pytest.raises(TradeQualityScoringEngineError):
        engine.score_candidates("not-a-list")


def test_empty_inputs_return_safe_empty_results() -> None:
    engine = TradeQualityScoringEngine()
    assert engine.score_candidates([]) == []
