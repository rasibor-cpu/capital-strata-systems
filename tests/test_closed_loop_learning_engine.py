from __future__ import annotations

import pytest

from backend.analytics.closed_loop_learning_engine import (
    ClosedLoopLearningEngine,
    ClosedLoopLearningEngineError,
)
from backend.analytics.strategy_memory_repository import StrategyMemoryRepository


def _completed_trade(trade_id="t-1", pnl=10.0, recommendation="EXECUTE", quality_score=82.0):
    return {
        "trade_id": trade_id,
        "timestamp_open": "2026-06-24T10:00:00+00:00",
        "timestamp_close": "2026-06-24T10:05:00+00:00",
        "symbol": "AAPL",
        "asset_class": "EQUITY",
        "entry_price": 100.0,
        "exit_price": 101.0,
        "quantity": 10.0,
        "realized_pnl": pnl,
        "holding_duration_seconds": 300.0,
        "strategy_id": "alpha",
        "market_regime": "TRENDING",
        "broker": "sim",
        "session": "regular",
        "volatility": 0.02,
        "trend_strength": 0.7,
        "confidence": 0.8,
        "recommendation": recommendation,
        "quality_score": quality_score,
    }


def test_closed_loop_learning_updates_memory(tmp_path) -> None:
    repo = StrategyMemoryRepository(tmp_path / "strategy_memory.json")
    repo.create_storage()
    engine = ClosedLoopLearningEngine(strategy_memory_repository=repo)

    result = engine.process_completed_trades([
        _completed_trade("t-1", pnl=10.0, recommendation="EXECUTE", quality_score=88.0),
        _completed_trade("t-2", pnl=-5.0, recommendation="WATCH", quality_score=52.0),
    ])

    assert result["updated_count"] == 2
    assert result["quality_feedback_summary"]["count"] == 2
    assert result["strategy_memory_summary"][0]["strategy_id"] == "alpha"


def test_invalid_inputs_fail_closed(tmp_path) -> None:
    repo = StrategyMemoryRepository(tmp_path / "strategy_memory.json")
    repo.create_storage()
    engine = ClosedLoopLearningEngine(strategy_memory_repository=repo)

    with pytest.raises(ClosedLoopLearningEngineError):
        engine.process_completed_trades(None)

    with pytest.raises(ClosedLoopLearningEngineError):
        engine.process_completed_trades([{"trade_id": "bad"}])


def test_empty_inputs_return_safe_empty_results(tmp_path) -> None:
    repo = StrategyMemoryRepository(tmp_path / "strategy_memory.json")
    repo.create_storage()
    engine = ClosedLoopLearningEngine(strategy_memory_repository=repo)

    result = engine.process_completed_trades([])
    assert result["updated_count"] == 0
    assert result["quality_feedback_summary"]["count"] == 0
