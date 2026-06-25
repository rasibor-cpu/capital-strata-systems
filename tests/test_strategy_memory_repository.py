from __future__ import annotations

import pytest

from backend.analytics.strategy_memory_repository import (
    DuplicateStrategyMemoryError,
    StrategyMemoryRepository,
    StrategyMemoryRepositoryError,
)


def _record(
    record_id: str,
    strategy_id: str = "mean_reversion",
    symbol: str = "EUR/USD",
    market_regime: str = "RANGING",
    pnl: float = 10.0,
    win: bool = True,
    confidence: float = 0.8,
) -> dict[str, object]:
    return {
        "record_id": record_id,
        "timestamp": "2026-06-24T12:00:00+00:00",
        "strategy_id": strategy_id,
        "symbol": symbol,
        "asset_class": "FX",
        "market_regime": market_regime,
        "session": "asia-open",
        "broker": "sim",
        "trade_id": f"trade-{record_id}",
        "realized_pnl": pnl,
        "win": win,
        "confidence": confidence,
    }


def test_persist_reload_and_aggregate_by_strategy(tmp_path) -> None:
    repo = StrategyMemoryRepository(tmp_path / "memory.json")
    repo.create_storage()

    repo.persist_memory_record(_record("r1", strategy_id="mean_reversion", pnl=10.0, win=True))
    repo.persist_memory_record(_record("r2", strategy_id="breakout", pnl=-5.0, win=False, confidence=0.6))
    repo.persist_memory_record(_record("r3", strategy_id="mean_reversion", pnl=3.0, win=True, confidence=0.9))

    rows = repo.load_records()
    aggregate = repo.aggregate_strategy_performance()

    assert len(rows) == 3
    mean = next(item for item in aggregate if item["strategy_id"] == "mean_reversion")
    assert mean["trade_count"] == 2
    assert mean["realized_pnl"] == 13.0
    assert mean["win_rate"] == 1.0


def test_duplicate_prevention(tmp_path) -> None:
    repo = StrategyMemoryRepository(tmp_path / "memory.json")
    repo.create_storage()

    repo.persist_memory_record(_record("r1"))
    with pytest.raises(DuplicateStrategyMemoryError):
        repo.persist_memory_record(_record("r1"))


def test_query_by_symbol_and_regime(tmp_path) -> None:
    repo = StrategyMemoryRepository(tmp_path / "memory.json")
    repo.create_storage()

    repo.persist_memory_record(_record("r1", symbol="EUR/USD", market_regime="RANGING"))
    repo.persist_memory_record(_record("r2", symbol="BTC/USD", market_regime="BREAKOUT"))

    eur_rows = repo.query_by_symbol("eur/usd")
    breakout_rows = repo.query_by_regime("breakout")

    assert len(eur_rows) == 1
    assert eur_rows[0]["symbol"] == "EUR/USD"
    assert len(breakout_rows) == 1
    assert breakout_rows[0]["market_regime"] == "BREAKOUT"


def test_corrupt_storage_fail_closed(tmp_path) -> None:
    path = tmp_path / "memory.json"
    path.write_text("not-json", encoding="utf-8")

    with pytest.raises(StrategyMemoryRepositoryError):
        StrategyMemoryRepository(path).load_records()
