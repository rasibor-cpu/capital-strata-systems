from __future__ import annotations

import pytest

from backend.analytics.strategy_intelligence_engine import (
    StrategyIntelligenceEngine,
    StrategyIntelligenceEngineError,
)
from backend.analytics.strategy_memory_repository import StrategyMemoryRepository


def _record(
    record_id: str,
    strategy_id: str,
    symbol: str,
    regime: str,
    pnl: float,
    win: bool,
    confidence: float,
) -> dict[str, object]:
    return {
        "record_id": record_id,
        "timestamp": "2026-06-24T12:00:00+00:00",
        "strategy_id": strategy_id,
        "symbol": symbol,
        "asset_class": "FX",
        "market_regime": regime,
        "session": "london-open",
        "broker": "sim",
        "trade_id": f"trade-{record_id}",
        "realized_pnl": pnl,
        "win": win,
        "confidence": confidence,
    }


def test_rank_strategies_by_context(tmp_path) -> None:
    repo = StrategyMemoryRepository(tmp_path / "memory.json")
    repo.create_storage()
    repo.persist_memory_record(_record("r1", "mean", "EUR/USD", "RANGING", 12.0, True, 0.9))
    repo.persist_memory_record(_record("r2", "breakout", "EUR/USD", "RANGING", -3.0, False, 0.6))
    repo.persist_memory_record(_record("r3", "mean", "EUR/USD", "RANGING", 4.0, True, 0.8))

    engine = StrategyIntelligenceEngine(repo)
    ranked = engine.rank_strategies_by_context(symbol="eur/usd", market_regime="ranging")

    assert len(ranked) == 2
    assert ranked[0]["strategy_id"] == "mean"


def test_best_strategy_for_symbol_and_regime(tmp_path) -> None:
    repo = StrategyMemoryRepository(tmp_path / "memory.json")
    repo.create_storage()
    repo.persist_memory_record(_record("r1", "trend", "BTC/USD", "BREAKOUT", 20.0, True, 0.95))
    repo.persist_memory_record(_record("r2", "mean", "BTC/USD", "BREAKOUT", -2.0, False, 0.5))

    engine = StrategyIntelligenceEngine(repo)

    best_symbol = engine.best_strategy_for_symbol("btc/usd")
    best_regime = engine.best_strategy_for_regime("breakout")

    assert best_symbol is not None
    assert best_regime is not None
    assert best_symbol["strategy_id"] == "trend"
    assert best_regime["strategy_id"] == "trend"


def test_confidence_scoring_and_summary(tmp_path) -> None:
    repo = StrategyMemoryRepository(tmp_path / "memory.json")
    repo.create_storage()
    repo.persist_memory_record(_record("r1", "mean", "EUR/USD", "RANGING", 5.0, True, 0.8))
    repo.persist_memory_record(_record("r2", "mean", "EUR/USD", "RANGING", 2.0, True, 0.6))

    engine = StrategyIntelligenceEngine(repo)

    confidence = engine.strategy_confidence("mean", symbol="EUR/USD")
    summary = engine.strategy_memory_summary()

    assert confidence == pytest.approx(0.7)
    assert summary["record_count"] == 2
    assert summary["strategy_count"] == 1


def test_empty_memory_behavior(tmp_path) -> None:
    repo = StrategyMemoryRepository(tmp_path / "memory.json")
    repo.create_storage()
    engine = StrategyIntelligenceEngine(repo)

    assert engine.rank_strategies_by_context(symbol="EUR/USD") == []
    assert engine.best_strategy_for_symbol("EUR/USD") is None
    assert engine.best_strategy_for_regime("RANGING") is None
    assert engine.strategy_memory_summary() == {}
    assert engine.strategy_confidence("mean") == 0.0


def test_fail_closed_on_invalid_inputs(tmp_path) -> None:
    repo = StrategyMemoryRepository(tmp_path / "memory.json")
    repo.create_storage()
    engine = StrategyIntelligenceEngine(repo)

    with pytest.raises(StrategyIntelligenceEngineError):
        engine.strategy_confidence("")
    with pytest.raises(StrategyIntelligenceEngineError):
        engine.rank_strategies_by_context(symbol="   ")
