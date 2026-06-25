from __future__ import annotations

import pytest

from backend.analytics.opportunity_ranking_engine import (
    OpportunityRankingEngine,
    OpportunityRankingEngineError,
)


def _row(trade_id, symbol, score, confidence):
    return {
        "trade_id": trade_id,
        "symbol": symbol,
        "quality_score": score,
        "confidence": confidence,
        "recommendation": "PREFERRED",
    }


def test_deterministic_ranking() -> None:
    engine = OpportunityRankingEngine()
    rows = [
        _row("t2", "MSFT", 75.0, 0.8),
        _row("t1", "AAPL", 75.0, 0.8),
        _row("t3", "TSLA", 82.0, 0.7),
    ]

    ranked = engine.rank(rows)

    assert [row["trade_id"] for row in ranked] == ["t3", "t1", "t2"]
    assert ranked == engine.rank(rows)


def test_top_n_and_minimum_quality_score() -> None:
    engine = OpportunityRankingEngine()
    rows = [
        _row("t1", "AAPL", 88.0, 0.9),
        _row("t2", "MSFT", 70.0, 0.7),
        _row("t3", "TSLA", 50.0, 0.6),
    ]

    ranked = engine.rank(rows, top_n=2, minimum_quality_score=60.0)
    assert [row["trade_id"] for row in ranked] == ["t1", "t2"]


def test_invalid_inputs_fail_closed() -> None:
    engine = OpportunityRankingEngine()

    with pytest.raises(OpportunityRankingEngineError):
        engine.rank("bad")
    with pytest.raises(OpportunityRankingEngineError):
        engine.rank([_row("t1", "AAPL", 80.0, 0.8)], top_n=0)


def test_empty_inputs_return_safe_empty_results() -> None:
    engine = OpportunityRankingEngine()
    assert engine.rank([]) == []
